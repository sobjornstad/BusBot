#!/usr/bin/env python
"""
Debugging tool that sends fake SMS requests to BusBot. You can use this to test
changes to BusBot without being charged for messages, as follows:

1. Change TO_URL to the URL of your app and TO_PHONE to your Twilio phone
   number.
2. Put BusBot into debug mode by setting DEBUG to True at the top of app.py,
   then deploying that version. This prevents it from actually sending out
   responses over SMS; it will just log what it would have sent.
3. Open 'heroku logs --tail' so you can see the messages that BusBot sends
   in response to your requests.
4. Call this tool like 'python testclient.py "my message" "my phone number".
   You can set DEFAULT_FROM_PHONE in the constants section below and thereafter
   leave the phone number out if you like.

Some of the data sent in the request will not be correct for your specific
phone number. BusBot does not use any content other than the from phone number
and the message currently, however.
"""

import requests
import sys

TO_URL = "https://MYAPPNAME.herokuapp.com/receivemsg"
TO_PHONE = "+10005551234"
DEFAULT_FROM_PHONE = "+10005551234"

if len(sys.argv) < 2:
    print("Usage: testclient.py MESSAGE_TO_SEND [PHONE_NUMBER_TO_SEND_FROM]")
    sys.exit(1)

message = sys.argv[1]
phone = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_FROM_PHONE

p = requests.post(TO_URL, data={
    'NumSegments': '1',
    'AccountSid': 'AC5d5d9a1e8d058c03484ea61ee11657c8',
    'MessageSid': 'SMa8ee1a60746a9814bb1e6ecaa4a81cc0',
    'FromZip': '46368',
    'MessagingServiceSid': 'MGd2d7909cbf1038f50158c18e735bce25',
    'FromState': 'IN',
    'NumMedia': '0',
    'ToState': 'MN',
    'SmsSid': 'SMa8ee1a60746a9814bb1e6ecaa4a81cc0',
    'FromCountry': 'US',
    'SmsMessageSid': 'SMa8ee1a60746a9814bb1e6ecaa4a81cc0',
    'ToCity': 'SPRING VALLEY',
    'FromCity': 'PORTAGE',
    'ToCountry': 'US',
    'Body': message,
    'To': TO_PHONE,
    'ApiVersion': '2010-04-01',
    'From': phone,
    'SmsStatus': 'received',
    'ToZip': '55975',
    })
print(p)
