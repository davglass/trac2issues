#!/usr/bin/env python

##Script to convert Trac Tickets to GitHub Issues

import re, os, sys, time, math, simplejson
import string, shutil, urllib2, urllib, pprint, simplejson, datetime
from datetime import datetime
from optparse import OptionParser

##Setup pp for debugging
pp = pprint.PrettyPrinter(indent=4)


parser = OptionParser()
parser.add_option('-t', '--trac', dest='trac', help='Path to the Trac project to export.')
parser.add_option('-p', '--project', dest='project', help='Name of the GitHub Project to import into.')
parser.add_option('-x', '--closed', action="store_true", default=False, dest='closed', help='Include closed tickets.')
parser.add_option('-c', '--component', action="store_true", default=False, dest='component', help='Create a label for the Trac component.')
parser.add_option('-m', '--milestone', action="store_true", default=False, dest='milestone', help='Create a label for the Trac milestone.')
parser.add_option('-o', '--owner', action="store_true", default=False, dest='owner', help='Create a label for the Trac owner.')
parser.add_option('-r', '--reporter', action="store_true", default=False, dest='reporter', help='Add a comment naming the reporter.')
parser.add_option('-u', '--url', dest='url', help='The base URL for the trac install (will also link to the old ticket in a comment).')

(options, args) = parser.parse_args(sys.argv[1:])




class ImportTickets:

    def __init__(self, trac=options.trac, project=options.project):
        self.env = open_environment(trac)
        self.trac = trac
        self.project = project
        self.now = datetime.now(utc)
        #Convert the timestamp from a float to an int to drop the .0
        self.stamp = int(math.floor(time.time()))
        self.github = 'https://github.com/api/v2/json'
        try:
            self.db = self.env.get_db_cnx()
        except TracError, e:
            print_error(e.message)

        self.includeClosed = options.closed
        self.labelMilestone = options.milestone
        self.labelComponent = options.component
        self.labelOwner = options.owner
        self.labelReporter = options.reporter
        self.useURL = False

        if options.url:
            self.useURL = "%s/ticket/" % options.url

        
        self.ghAuth()
        
        self.checkProject()

        if self.useURL:
            print bold('Does this look like a valid trac url? [y/N]\n %s1234567' % self.useURL)
            go = sys.stdin.readline().strip().lower()

            if go[0:1] != 'y':
                print_error('Try Again..')
            
        ##We own this project..
        self._fetchTickets()

    def checkProject(self):
        url = "%s/repos/show/%s/%s" % (self.github, self.login, self.project)
        data = simplejson.load(urllib.urlopen(url))
        if 'error' in data:
            print_error("%s/%s: %s" % (self.login, self.project, data['error'][0]['error']))
        

    def ghAuth(self):
        login = os.popen('git config --global github.user').read().strip()
        token = os.popen('git config --global github.token').read().strip()

        if not login:
            print_error('GitHub Login Not Found')
        if not token:
            print_error('GitHub Token Not Found')

        self.login = login
        self.token = token

    def _fetchTickets(self):
        cursor = self.db.cursor()        
        
        where = " where (status != 'closed') "
        if self.includeClosed:
            where = ""

        sql = "select id, summary, description, milestone, component, reporter, owner from ticket %s order by id" % where
        cursor.execute(sql)
        # iterate through resultset
        tickets = []
        for id, summary, description, milestone, component, reporter, owner in cursor:
            ticket = {
                'id': id,
                'summary': summary,
                'description': description,
                'milestone': milestone.replace(' ', '_'),
                'component': component.replace(' ', '_'),
                'reporter': reporter.replace(' ', '_'),
                'owner': owner.replace(' ', '_'),
                'history': []
            }
            cursor2 = self.db.cursor()        
            sql = 'select author, time, newvalue from ticket_change where (ticket = %s) and (field = "comment")' % id
            cursor2.execute(sql)
            for author, time, newvalue in cursor2:
                change = {
                    'author': author,
                    'time': time,
                    'comment': newvalue
                }
                ticket['history'].append(change)

            tickets.append(ticket)

        print bold('About to import (%s) tickets from Trac to %s/%s.\n%s? [y/N]' % (len(tickets), self.login, self.project, red('Are you sure you wish to continue')))
        go = sys.stdin.readline().strip().lower()

        if go[0:1] != 'y':
            print_error('Import Aborted..')


        #pp.pprint(tickets)
        for data in tickets:
            self.createIssue(data)

        
    def createIssue(self, info):
        print bold('Creating issue.')
        out = {
            'login': self.login,
            'token': self.token,
            'title': info['summary'],
            'body': info['description']
        }
        data = urllib.urlencode(out)

        url = "%s/issues/open/%s/%s" % (self.github, self.login, self.project)
        req = urllib2.Request(url, data)
        response = urllib2.urlopen(req)
        ticket_data = simplejson.load(response)

        if 'number' in ticket_data['issue']:
            num = ticket_data['issue']['number']
            print bold('Issue #%s created.' % num)
        else:
            print_error('GitHub didn\'t return an issue number :(')

        if self.labelMilestone and 'milestone' in info:
            self.createLabel(num, "M:%s" % info['milestone'])

        if self.labelComponent and 'component' in info:
            self.createLabel(num, "C:%s" % info['component'])

        if self.labelOwner and 'owner' in info:
            self.createLabel(num, "@%s" % info['owner'])

        if self.labelReporter and 'reporter' in info:
            self.createLabel(num, "@@%s" % info['reporter'])
        
        for i in info['history']:
            comment = "Author: %s\n%s" % (i['author'], i['comment'])
            self.addComment(num, comment)

        if self.useURL:
            comment = "Ticket imported from Trac:\n %s%s" % (self.useURL, info['id'])
            self.addComment(num, comment)
            

    def createLabel(self, num, name):
        print bold("\tAdding label %s to issue # %s" % (name, num))
        url = "%s/issues/label/add/%s/%s/%s/%s" % (self.github, self.login, self.project, name, num)
        out = {
            'login': self.login,
            'token': self.token
        }
        data = urllib.urlencode(out)
        req = urllib2.Request(url, data)
        response = urllib2.urlopen(req)
        label_data = simplejson.load(response)
        
    def addComment(self, num, comment):
        print bold("\tAdding comment to issue # %s" % num)
        url = "%s/issues/comment/%s/%s/%s" % (self.github, self.login, self.project, num)
        out = {
            'login': self.login,
            'token': self.token,
            'comment': comment
        }
        data = urllib.urlencode(out)
        req = urllib2.Request(url, data)
        response = urllib2.urlopen(req)
        
        

##Format bold text
def bold(str):
    return "\033[1m%s\033[0m" % str

##Format red text (for errors)
def red(str):
    return "\033[31m%s\033[0m" % str

##Print and format an error, then exit the script
def print_error(str):
    print  bold(red(str))
    sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print "For usage: %s --help" % (sys.argv[0])
        print
    else:
        if not options.trac or not options.project:
            print_error("For usage: %s --help" % (sys.argv[0]))

        os.environ['PYTHON_EGG_CACHE'] = '/tmp/.egg-cache'
        os.environ['TRAC_ENV'] = options.trac
        from trac.core import TracError
        from trac.env import open_environment
        from trac.ticket import Ticket
        from trac.ticket.web_ui import TicketModule
        from trac.util.text import to_unicode
        from trac.util.datefmt import utc
        ImportTickets()



'''
    def _fetchTickets(self):
        changetime = self.stamp - (60 * 60 * 24 * 9)
        cursor = self.db.cursor()
        sql = "select id, summary from ticket where (status = 'infoneeded') and (changetime < %i)" % changetime
        cursor.execute(sql)
        result = cursor.fetchall()
        # iterate through resultset
        for record in result:
            print("Expiring Ticket: #%s :: %s :: %s" % (record[0], record[1], self.project))
            ticket = Ticket(self.env, record[0], self.db)
        
            # determine sequence number... 
            cnum = 0
            tm = TicketModule(self.env)
            for change in tm.grouped_changelog_entries(ticket, self.db):
                if change['permanent']:
                    cnum += 1
            
            ticket['status'] = 'closed'
            ticket['resolution'] = 'expired'
            ticket.save_changes('trac-bot', 'Ticket automatically closed due to no activity.', self.now, self.db, cnum+1)
            self.db.commit()
            tn = TicketNotifyEmail(self.env)
            tn.notify(ticket, newticket=0, modtime=self.now)
'''
