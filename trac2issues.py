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

(options, args) = parser.parse_args(sys.argv[1:])




class ImportTickets:

    def __init__(self, trac=options.trac, project=options.project):
        self.env = open_environment(trac)
        self.trac = trac
        self.project = project
        self.now = datetime.now(utc)
        #Convert the timestamp from a float to an int to drop the .0
        self.stamp = int(math.floor(time.time()))
        self.github = 'http://github.com/api/v2/json'
        try:
            self.db = self.env.get_db_cnx()
        except TracError, e:
            print_error(e.message)

        self.ghAuth()
        
        self.checkProject()

    def checkProject(self):
        url = "%s/repos/show/%s/%s" % (self.github, self.login, self.project)
        data = simplejson.load(urllib.urlopen(url))
        if 'error' in data:
            print_error("%s/%s: %s" % (self.login, self.project, data['error'][0]['error']))
        
        ##We own this project..
        print bold('Nothing more from here, pending GitHub issues API updates')

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
        print bold(red('_fetchTickets'))


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
