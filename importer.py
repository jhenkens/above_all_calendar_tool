from __future__ import print_function
import httplib2
import os
import re
from apiclient import discovery
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage
from datetime import datetime, timedelta, timezone
import pytz
import json

try:
    import argparse
    ap = argparse.ArgumentParser(parents=[tools.argparser])
    ap.add_argument('--file', type=argparse.FileType('r'))
    flags = ap.parse_args()
except ImportError:
    flags = None

import sys

def query_yes_no(question, default="yes"):
    """Ask a yes/no question via input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
        It must be "yes" (the default), "no" or None (meaning
        an answer is required of the user).

    The "answer" return value is True for "yes" or False for "no".
    """
    valid = {"yes": True, "y": True, "ye": True,
             "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        sys.stdout.write(question + prompt)
        choice = input().lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' "
                             "(or 'y' or 'n').\n")

# If modifying these scopes, delete your previously saved credentials
# at ~/.credentials/calendar-python-quickstart.json
SCOPES = 'https://www.googleapis.com/auth/calendar'
CLIENT_SECRET_FILE = 'client_secret.json'
APPLICATION_NAME = 'Google Calendar API Python Quickstart'


def get_credentials():
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """
    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir,
                                   'calendar-python-quickstart.json')

    store = Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        if flags:
            credentials = tools.run_flow(flow, store, flags)
        else: # Needed only for compatibility with Python 2.6
            credentials = tools.run(flow, store)
        print('Storing credentials to ' + credential_path)
    return credentials

def main():
    """Shows basic usage of the Google Calendar API.

    Creates a Google Calendar API service object and outputs a list of the next
    10 events on the user's calendar.
    """
    credentials = get_credentials()
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('calendar', 'v3', http=http)

    print('Getting the upcoming 10 events')
    cals = service.calendarList().list().execute().get('items',[])
    kj = 'K & J'
    fl = 'Flight Lessons'
    kj_id = next(obj['id'] for obj in cals if obj['summary'] == kj)
    fl_id = next(obj['id'] for obj in cals if obj['summary'] == fl)
    print(kj + " :: " + kj_id)
    print(fl + " :: " + fl_id)
    deleteFromCalendar(service, kj, kj_id)
    deleteFromCalendar(service, fl, fl_id)

    events = parseEvents()
    if events:
        addEventsToCalendar(service,kj,kj_id,events,None)
        addEventsToCalendar(service,fl,fl_id,events,1)
        addEventsToCalendar(service,fl,fl_id,events,24)


def addEventsToCalendar(service, desc, calid,events, alarm):
    alarm_desc = "no alarm"
    alarms = []
    if alarm:
        alarm_desc = "a alarm " +str(alarm) + " hours before"
        alarms = [{'minutes':alarm*60,'method':'popup'}]
    if (query_yes_no("Add events to " + desc + " with " + alarm_desc + "?")):
        for event in events:
            body = {
                'summary': "AboveAll: " + event['instructor'] + " with " + event['plane'],
                'start':{'dateTime': event['start'].isoformat()},
                'end':{'dateTime': event['end'].isoformat()},
                'location': '1503 Cook Pl, Santa Barbara, CA 93117',
                'reminders':{
                    'useDefault': False,
                    'overrides': alarms
                    }
                }
            service.events().insert(
                calendarId=calid,
                body=body
            ).execute()


def getDateTime(string):
    time_format = "%m/%d/%y %H:%M%p"
    date = datetime.strptime(string + "M", time_format)
    date = pytz.timezone('US/Pacific').localize(date)
    return date

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError ("Type %s not serializable" % type(obj))

def parseEvents():
    if(not flags.file):
        print("No file given to parse")
        return None
    regex = re.compile('(.*) beginning (.*) (?:until|through) (.*)')
    result = []
    lines = [line for line in flags.file]
    now = datetime.now(timezone.utc)
    for f in lines:
        f = f.strip()
        if f:
            match = regex.match(f)
            if match:
                start = getDateTime(match.group(2))
                if(start < now): continue

                event = next((e for e in result if e['start'] == start),None)
                if(not event):
                    event = {}
                    event['plane'] = "no plane"
                    result.append(event)

                event['start'] = start
                event['end'] = getDateTime(match.group(3))
                if ("172" in match.group(1) or "152" in match.group(1)):
                    event['plane'] = match.group(1)
                else:
                    event['instructor'] = match.group(1)
    bad_events = [e for e in result if not 'instructor' in e]
    if bad_events:
        raise Exception("Every lesson needs and instructor")
    if(result):
        print(json.dumps(result, indent=4, sort_keys=True, default=str))
    return result

def deleteFromCalendar(service, desc, calid):
    now = datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
    print("Looking for future AboveAll notifications in " + desc + "...")
    eventsResult = service.events().list(
        calendarId=calid, timeMin=now, singleEvents=True,
        orderBy='startTime', q='AboveAll'
        ).execute()
    events = eventsResult.get('items', [])
    if not events:
        print('No upcoming events found.')
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        print(start, event['summary'])
    if events and query_yes_no("Removing future lessons from " + desc + "?", "no"):
        for event in events:
            service.events().delete(calendarId=calid, eventId=event['id']).execute()
        print("Done deleting from " + desc)




if __name__ == '__main__':
    main()
