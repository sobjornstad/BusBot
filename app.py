"""
Flask app that processes requests and keeps track of the user database.

See README.md for documentation.
"""

import os
import string
import traceback
from urllib.parse import urlparse

from flask import Flask, request
import psycopg2
from twilio.rest import TwilioRestClient

## CONSTANTS ##
TWILIO_ACCOUNT_SID = ""
TWILIO_AUTH_TOKEN = ""
OUR_NUMBER = "+10005551234"
SUPERUSER = "+10005551234"

# if true, we will log messages but not actually send them
DEBUG = False

# Set up database
url = urlparse(os.environ["DATABASE_URL"])
db_conn = psycopg2.connect(
    database=url.path[1:],
    user=url.username,
    password=url.password,
    host=url.hostname,
    port=url.port
)

# Set up other objects
sms_client = TwilioRestClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
app = Flask(__name__)


### Generic helper functions ###
def send_msg(to_phone, body):
    "Send message /body/ to phone number /phone/."
    print("==> %s :: %s" % (to_phone, body))
    if not DEBUG:
        sms_client.messages.create(
            to=to_phone, from_=OUR_NUMBER, body=body)

def send_all(body):
    "Send /body/ to ALL users on the list. Use with caution."
    cursor = db_conn.cursor()
    cursor.execute("SELECT phone FROM users")
    for user_phone in cursor.fetchall():
        send_msg(user_phone[0], body)

def notify_counters(body):
    "Send /body/ to all bus counters."
    cursor = db_conn.cursor()
    cursor.execute("SELECT phone FROM users WHERE iscounter = True")
    for counter_phone in cursor.fetchall():
        send_msg(counter_phone[0], body)

def get_user(msg_phone):
    """
    Return a dictionary with information about the user with given phone.
    """
    cursor = db_conn.cursor()
    cursor.execute("""SELECT firstname, lastname, curstatus, iscounter
                      FROM users WHERE phone = %s""",
                   (msg_phone,))
    user_info = cursor.fetchone()
    if user_info is None:
        return None
    else:
        firstname, lastname, curstatus, iscounter = user_info
        return {'firstname': firstname, 'lastname': lastname,
                'phone': msg_phone, 'curstatus': curstatus,
                'iscounter': iscounter}

def get_displayname(firstname, lastname):
    "Determine if user's last name is necessary for disambiguation."
    cursor = db_conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE firstname = %s", (firstname,))
    if cursor.fetchone()[0] > 1:
        displayname = "%s %s" % (firstname, lastname)
    else:
        displayname = firstname
    return displayname

def get_displayname_from_userinfo(userinfo):
    return get_displayname(userinfo['firstname'], userinfo['lastname'])

def is_buscounter(user_info):
    return user_info['iscounter']

def is_superuser(user_info):
     return user_info['phone'] == SUPERUSER

# The superuser may want to have bus counter *privileges* without actually
# receiving all the notifications destined for bus counters.
def has_buscounter_privileges(user_info):
    return is_buscounter(user_info) or is_superuser(user_info)

def set_status_bit(bit, value):
    """
    Set a status bit to a given value.

    Status bits are stored as columns of a single row of the 'status' table.
    The recreate_database.py script needs to be changed if more bits are added,
    since the database schema will be changing.

    Right now the only status bit is 'all_in', which means that all the users
    have marked themselves IN or ABSENT at the present moment (this lets BusBot
    notify the bus counters when someone marks themself OUT in only the case
    that everyone was previously IN).
    """
    if bit == 'all_in':
        query = 'UPDATE status SET all_in = %s'
        params = (value,)
    else:
        assert False, "Whoops! That status bit doesn't exist!"
    cursor = db_conn.cursor()
    cursor.execute(query, params)
    db_conn.commit()

def get_status_bit(bit):
    "Get the value of a status bit (see set_status_bit())."
    cursor = db_conn.cursor()
    if bit == 'all_in':
        query = 'SELECT all_in FROM status LIMIT 1'
    else:
        assert False, "Whoops! That status bit doesn't exist!"
    cursor.execute(query)
    return cursor.fetchone()[0]

def check_global_status():
    """
    Function called every time BusBot receives a message to do housekeeping and
    check if certain states now obtain.
    """
    if not find_missing() and not get_status_bit('all_in'):
        cursor = db_conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users WHERE curstatus = 'ABSENT'")
        not_riding = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users WHERE curstatus = 'IN'")
        headcount = cursor.fetchone()[0]
        notify_counters("Everyone is now marked as IN or ABSENT. %s total "
                        "people, %s NOTRIDING. Head count should be %s."
                        % (total, not_riding, headcount))
        set_status_bit('all_in', True)

def parse_user_selector(selector):
    """
    Parse string /selector/ as a phone number, first name, or first&last name.
    Return an error string on failure or a user dictionary on success.
    """
    def name_split_possibilities(userstring):
        """
        Generator for all the possible ways to split a name on spaces, so we
        can match names like "Vincent van Gogh" or "Mary Kate Smith" without
        having to worry if the part in the middle is part of the first or the
        last name. (If this creates ambiguity, so be it, it would be too
        confusing to use anything but the phone number for selection anyway.)

        Generator is empty if there are no spaces in userstring.
        """
        parts = userstring.split(' ')
        if len(parts) == 1:
            return
        for spliton in range(len(userstring) + 1):
            yield ' '.join(parts[:spliton]), ' '.join(parts[spliton:])

    cursor = db_conn.cursor()

    ## First attempt: phone number
    if selector.startswith('+1') and len(selector) == 12:
        possible_phonenum = selector
    else:
        possible_phonenum = '+1' + ''.join(i for i in selector
                                           if i not in string.punctuation + ' ')
    if len(possible_phonenum) == 12:
        cursor.execute("SELECT phone FROM users WHERE phone = %s",
                       (possible_phonenum,))
        found = cursor.fetchone()
        if found:
            return get_user(found[0]) # success

    ## Second attempt: first name
    cursor.execute("""SELECT firstname, lastname, phone
                      FROM users WHERE LOWER(firstname) = %s""", (selector,))
    results = cursor.fetchall()
    if len(results) == 1:
        return get_user(results[0][2]) # success
    elif len(results):
        possibles = [' '.join(i[0:2]) for i in results]
        msg = "Person ambiguous; did you mean one of: " + ", ".join(possibles)
        return msg # failure

    ## Third attempt: first and last name
    for firstname, lastname in name_split_possibilities(selector):
        cursor.execute("""SELECT firstname, lastname, phone
                          FROM users
                          WHERE LOWER(firstname) = %s
                                AND LOWER(lastname) = %s""",
                       (firstname, lastname))
        results = cursor.fetchall()
        if len(results) == 1:
            return get_user(results[0][2]) # success
        elif len(results):
            # failure
            return ("There appear to be two people by that name in the "
                    "database. Please use the person's phone number.")

    return ("Sorry, I couldn't work out who you meant. I understand 10-digit "
            "phone numbers, first names, and first&last names.")


### Changing a user's status ###
def mark_user(user_info, status):
    """
    Set a user's status to a value in the database. Don't call this function by
    itself -- use the helper functions below, since they sometimes take other
    actions as well.
    """
    cursor = db_conn.cursor()
    cursor.execute("UPDATE users SET curstatus = %s WHERE phone = %s",
                   (status, user_info['phone']))
    db_conn.commit()
    print("Marked user %s as %s." % (user_info['firstname'], status))

def mark_user_in(user_info):
    mark_user(user_info, 'IN')
    return None

def mark_user_out(user_info):
    mark_user(user_info, 'OUT')
    # If everyone *was* on the bus, but this person just got off,
    # a warning is in order.
    if get_status_bit('all_in'):
        notify_counters("WARNING: %s marked themselves OUT. Don't leave yet!"
                        % get_displayname_from_userinfo(user_info))
    set_status_bit('all_in', False)
    return "You have been marked as OUT and may safely step off the bus."

def mark_user_absent(user_info):
    mark_user(user_info, 'ABSENT')
    return None

def mark_user_wait(user_info):
    mark_user(user_info, 'WAIT')
    notify_counters("%s is on their way, please hold the bus!"
                    % get_displayname_from_userinfo(user_info))
    set_status_bit('all_in', False)
    return None

def get_user_status(user_info):
    if user_info['curstatus'] == 'UNSET':
        return "You have not yet checked in. Reply IN, WAIT, or ABSENT to set your status."
    else:
        return "You are currently marked as %s. Reply IN, OUT, WAIT, or ABSENT to change." % user_info['curstatus']

def markas(user_info, msg_command):
    "Set another user as checked in."

    def set_other(setter, settee, status):
        status = status.upper()
        if status not in ('IN', 'OUT', 'ABSENT', 'WAIT'):
            return "You may only mark someone as IN, OUT, ABSENT, or WAIT."
        {'IN': mark_user_in, 'OUT': mark_user_out,
         'ABSENT': mark_user_absent, 'WAIT': mark_user_wait
        }[status](settee)
        send_msg(settee['phone'], "Notice: %s marked you as %s."
                 % (get_displayname_from_userinfo(setter), status))

        if status == 'OUT':
            return ("%s has been marked as OUT and may safely step off the "
                    "bus." % get_displayname_from_userinfo(settee))
        return None

    try:
        body = msg_command.lower().split('mark ', 1)[1].strip()
        user, status = (i.strip() for i in body.split(' as '))
    except ValueError:
        return ("Sorry, I'm not sure what you meant. Use MARK user AS status, "
                "where user is a phone, first name, or first&last name.")

    user_or_error = parse_user_selector(user)
    if isinstance(user_or_error, dict): # user
        return set_other(user_info, user_or_error, status)
    else: # error
        return user_or_error

### Bus counter commands ###
def reset_status_generic(user_info):
    """
    The part of resetting that happens regardless of whether it's a hard or
    soft reset.
    """
    cursor = db_conn.cursor()
    cursor.execute("UPDATE users SET curstatus = 'UNSET'")
    db_conn.commit()
    set_status_bit('all_in', False)

def soft_reset(user_info):
    "Reset all users' statuses to UNSET and notify bus counters."
    if not has_buscounter_privileges(user_info):
        return "Only bus counters can reset the count."
    reset_status_generic(user_info)
    notify_counters("Bus counts have been reset.")

def hard_reset(user_info):
    """
    Reset all users' status to UNSET and notify *everyone*. This is generally
    obnoxious and expensive.
    """
    if not has_buscounter_privileges(user_info):
        return "Only bus counters can reset the count."
    reset_status_generic(user_info)
    send_all("Sorry, we got mixed up! If you checked in already, please do so again.")
    notify_counters("Bus counts have been hard-reset. Be more careful next time!")

def find_missing():
    "Return a list of people who are not marked as ABSENT or IN."
    # NOTE: Make sure user is a counter before calling this function!
    cursor = db_conn.cursor()
    cursor.execute("""SELECT firstname, lastname, phone, curstatus
                      FROM users WHERE curstatus NOT IN ('ABSENT', 'IN')""")
    people = []
    for i in cursor.fetchall():
        firstname, lastname, phone, curstatus = i
        displayname = get_displayname(firstname, lastname)
        people.append((displayname, phone, curstatus))
    return people

def list_missing(user_info):
    """
    Format the find_missing() list and send it to the bus counter requesting
    it.
    """
    if not has_buscounter_privileges(user_info):
        return "Only bus counters can see who's missing."
    missing = find_missing()
    if not missing:
        return "Everyone is marked as on the bus or not riding."
    if len(missing) > 15:
        return "%i people are still missing. (When 15 or fewer are missing, they will be listed by name.)" % len(missing)
    else:
        return '; '.join("%s - %s" % (i[0], i[2]) for i in missing)

def ping_missing(user_info):
    """
    Send a text to everyone in the find_missing() list asking them to set their
    status.
    """
    if not has_buscounter_privileges(user_info):
        return "Only bus counters can ping missing people."
    missing = find_missing()
    if not missing:
        send_msg(user_info['phone'], "Everybody is marked as on the bus or not riding!")
        return
    notify_counters("Ping sent to all %i missing people." % len(missing))
    for displayname, phone, curstatus in missing:
        send_msg(phone, "Hey, the bus counters are looking for you! Please reply IN (I'm on the bus and forgot to check in), WAIT (I'm on my way), or ABSENT (I'm not riding the bus).")

def show_absent(user_info):
    """
    Show a list of everyone who has marked themselves as ABSENT; the command
    for this is NOTRIDING.
    """
    if not has_buscounter_privileges(user_info):
        return "Only bus counters can list absent people."
    cursor = db_conn.cursor()
    cursor.execute("""SELECT firstname, lastname
                      FROM users WHERE curstatus = 'ABSENT'""")
    people = []
    for i in cursor.fetchall():
        firstname, lastname = i
        displayname = get_displayname(firstname, lastname)
        people.append(displayname)
    if people:
        return 'Absent: ' + ', '.join(people)
    else:
        return 'Nobody is currently marked as absent.'


### Miscellaneous ###
def show_help(user_info, was_failure=False):
    """
    Send a help message to the user who requested it or typed an invalid
    command, showing all commands the user has permissions to use.
    """
    if was_failure:
        send_body = "***Invalid command.*** "
    else:
        send_body = ""
    send_body += "Mark status as: IN, OUT, WAIT, ABSENT; otherwise STATUS, WHOIS [user], WHOAMI, MARK [user] AS [status]. "
    if has_buscounter_privileges(user_info):
        send_body += "Bus counters: LIST, PING, NOTRIDING, RESET, HARDRESET. "
    if is_superuser(user_info):
        send_body += "Superuser: WALL, PROMOTE, DEMOTE. "
    send_body += "Full help: http://goo.gl/CsTLwM"
    return send_body

def whoami(user_info):
    """
    Return a formatted version of the user_info dictionary.
    """
    msg = "FN %(firstname)s - LN %(lastname)s - PHONE %(phone)s - STATUS %(curstatus)s"
    if is_buscounter(user_info):
        msg += " - BUS COUNTER"
    if is_superuser(user_info):
        msg += " - SUPERUSER"
    return msg % user_info

def whois(user_info, msg_command):
    """
    Call whoami() on a specific person.
    """
    try:
        selector = msg_command.lower().split('whois ', 1)[1].strip()
    except IndexError:
        return "Usage: WHOIS [user], where user is a phone number, first name, or first&last name."
    user_to_find = parse_user_selector(selector)
    if isinstance(user_to_find, dict): # returned success
        return whoami(user_to_find)
    else: # not found, error message
        return user_to_find

def wall(user_info, msg_command):
    "Send a message to everyone; only usable by superuser."
    if not is_superuser(user_info):
        return "Only the superuser may use WALL (send message to all users)."

    body = msg_command[5:]
    send_all(body)

def mod_bus_counter_privileges(user_selector, will_be_counter):
    """
    Promote or demote a user to/from bus counter privileges. Call this function
    through promote_user() or demote_user().
    """
    try:
        selector = user_selector.lower().split('mote ', 1)[1].strip()
    except IndexError:
        return "Usage: PROMOTE/DEMOTE [user], where user is a phone number, first name, or first&last name."
    user_to_promote = parse_user_selector(selector)
    if isinstance(user_to_promote, dict): # returned success
        cursor = db_conn.cursor()
        assert type(will_be_counter) == bool
        cursor.execute("UPDATE users SET iscounter = %s WHERE phone = %s",
                       (will_be_counter, user_to_promote['phone']))
        db_conn.commit()
        if will_be_counter:
            send_msg(user_to_promote['phone'], "You are now a bus counter.")
        else:
            send_msg(user_to_promote['phone'], "You are no longer a bus counter.")
    else: # not found, error message
        return user_to_promote

def promote_user(user_info, msg_command):
    if not is_superuser(user_info):
        return "Only the superuser may use PROMOTE."
    return mod_bus_counter_privileges(msg_command, True)

def demote_user(user_info, msg_command):
    if not is_superuser(user_info):
        return "Only the superuser may use DEMOTE."
    return mod_bus_counter_privileges(msg_command, False)

# Dispatch table. Functions receive one argument, the user info dictionary, and
# may return either None or a string they'd like to reply with.
dispatch_onearg = {'COMMANDS': show_help,
                   'IN': mark_user_in,
                   'OUT': mark_user_out,
                   'ABSENT': mark_user_absent,
                   'WAIT': mark_user_wait,
                   'STATUS': get_user_status,
                   'WHOAMI': whoami,
                   # following commands are for bus counters only
                   'RESET': soft_reset,
                   'HARDRESET': hard_reset,
                   'LIST': list_missing,
                   'PING': ping_missing,
                   'NOTRIDING': show_absent,
                   }

# These are the same but they take the user info dictionary and the full text
# of the message body (so they can parse arguments from it).
dispatch_twoarg = {'WALL': wall,
                   'MARK': markas,
                   'WHOIS': whois,
                   'PROMOTE': promote_user,
                   'DEMOTE': demote_user,
                   }

@app.route('/receivemsg', methods=['POST'])
def receive_msg():
    """
    This function runs every time Twilio forwards an incoming SMS message to
    our app. It searches for an appropriate function in the dispatch tables
    above and returns an "invalid command" message if not.

    If a function returns something other than None, the return value is sent
    as a reply to the user who originally sent the message.
    """
    try:
        if request.method == "POST":
            # Parse incoming message.
            msg_was_from = request.form["From"]
            msg_body = request.form["Body"]
            msg_command = msg_body.upper().strip()
            print("<~~ %s :: %s" % (msg_was_from, msg_body))

            # Do something with it.
            user_info = get_user(msg_was_from)
            if user_info is None:
                print("Phone number %s was not in database, message rejected."
                      % msg_was_from)
                # We return 200 so twilio doesn't freak out. Consider if we
                # should send an explanatory message; the downside of that is
                # that random people sending spam to our number will cost us
                # extra money.
                return 'phone not in our database', 200

            function = msg_command.split(' ')[0]
            if ((function not in dispatch_onearg) and (function not in dispatch_twoarg)):
                retval = show_help(user_info, True)
            elif function in dispatch_onearg:
                retval = dispatch_onearg[function](user_info)
            elif function in dispatch_twoarg:
                retval = dispatch_twoarg[function](user_info, msg_body.strip())
            else:
                print(function)

            if retval is not None:
                send_msg(msg_was_from, retval)

            check_global_status()
            return 'success', 200

    except Exception:
        print(traceback.format_exc())
        send_msg(SUPERUSER, "Error thrown in request from %s." % msg_was_from)
        send_msg(msg_was_from, "Sorry, I goofed! Your request was not "
                 "completed. This error has been logged.")
        return 'error', 200


if __name__ == '__main__':
    app.run(debug=True)
