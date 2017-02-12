BusBot is an SMS chatbot that helps large traveling groups avoid leaving people
behind. Users text `IN` to a special phone number once they’re sitting on the
bus, then “bus counters” with special privileges can check who’s still missing
and send reminder texts to anyone who hasn’t checked in.

It is composed of a [Flask][Flask-link] app used in conjunction with
[Twilio][tw-link] for SMS communications. It can be easily and effectively
hosted for free on the [Heroku][Heroku-link] cloud platform.

[tw-link]: https://www.twilio.com/
[Flask-link]: http://flask.pocoo.org/
[Heroku-link]: https://www.heroku.com/

Additional features include:

* OUT, WAIT, and ABSENT statuses for times when people get on the bus and then
  have to leave, are running late, or aren’t riding at all;
* A WHOIS function for people in the group to easily get each other’s phone
  numbers and other information;
* A WALL function (“write all,” like the Unix command) for the superuser to
  send a message to everyone on the list.

A basic working knowledge of Unix server management or webapp development will
be helpful in setting up the server (see instructions below), but it’s fairly
straightforward. Users only need to know how to send and receive text messages.


Cost
====

A Heroku free tier dyno should be sufficient, so there will be no cost from
Heroku. You get several hundred hours of time per month, which only counts time
the dyno is actually doing work. Unless you’re doing check-ins very frequently,
the dyno will likely be sitting idle for 22 hours a day.

(For the sake of completeness, heroku’s free `hobby-dev` databases are limited
to 10,000 rows, but BusBot uses only one more row than there are users. If you
have more than 9,999 people in your group, heaven help you!)

Twilio charges $1.00/month to maintain a phone number and $0.0075
(three-quarters of a cent) per text sent or received. For my recent tour group
of about 90 people, I found it cost us just about a dollar per check-in. At
three-quarters of a cent, you get 133 messages to the dollar (rounded down).
All members sending an `IN` takes 90 messages, which leaves 43 for other
functions like requesting help, checking out and in again, using WAIT and
ABSENT to notify the bus counters, and getting pinged by the bus counters.

That’s substantial but not excessive, especially given the bother and expense
if somebody misses the bus – in terms of total expenditure by the group, one
person getting left behind once and having to pay for transportation to catch
up may cost more!


Server setup
============

These steps were tested on a Linux Mint machine. They’ll probably take about
half an hour to complete.

1. Sign up for a Heroku account (http://heroku.com) and install the Heroku
   toolchain and command-line interface. Heroku will host the server logic that
   stores users’ statuses and responds to texts. There are plenty of guides out
   there to help you with this step if you have trouble.

2. Open a terminal, clone down the BusBot repository, and change directory into
   it.

3. Create a new Heroku app (`heroku create APP_NAME`; you can use any app name
   you like). Add a Postgres database to it with `heroku addons:create
   heroku-postgresql:hobby-dev`. Then `heroku pg:wait`, which will block until
   the database is ready (this only took a second for me, but the docs say it
   may take up to 5 minutes).

4. Install Postgres on your machine so you can set up the database (and edit it
   manually should it be necessary). Ideally this would be a machine you bring
   with you on your travels or can `ssh` into, as you’ll need Postgres to make
   changes to the user database if necessary for some reason. Once Postgres is
   installed, try connecting with `heroku pg:psql`; you should receive a
   database prompt. If there are errors, get them ironed out before continuing.

5. Sign up for a Twilio account (http://twilio.com). There is a free trial to
   make sure things work before you have to start paying for it. Verify your
   phone number, create a new application, and create a phone number for it (it
   will say “BUY”, but the first number is free on a free trial).

6. Edit `app.py` and set `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and
   `OUR_NUMBER` (the number you signed up for in the previous step) as
   appropriate. Set `SUPERUSER` to your own phone number (beginning with `+1`
   for the USA). This number, unlike other numbers, has the right to grant
   permissions and use the WALL command. It also has bus counter privileges but
   will not receive bus counter notifications unless also made a bus counter
   with PROMOTE.

7. Deploy the app to Heroku – first `git commit -am "setup parameters"`, then
   `git push heroku master`. If any errors come up, you’ll have to work out
   what the problem was and fix it, but hopefully everything will go smoothly.

8. Run `heroku info APP_NAME` and copy the web URL. Go to the Twilio console
   and click the bubble on the left (“Programmable SMS”), then “Messaging
   Services” in the sidebar, then your app. Set the **Request URL** to the URL
   you copied with `receivemsg` appended (so it will look something like
   `http://YOURAPPNAME.herokuapp.com/receivemsg`). Twilio will POST to this URL
   anytime it receives a text, thereby notifying the bus counter app.

   It’s a good idea to fill the same URL in as the “Fallback URL.” This is
   because Twilio considers that its request has timed out after 15 seconds,
   and Heroku free instances occasionally take just a smidgen longer than that
   to wake up after being idle for a while. In such a case, the request will
   fail, but it will almost certainly succeed if Twilio tries the exact same
   request again.

9. Create a CSV file containing users and phone numbers. It should have three
   columns, separated by commas: first names, last names, and phone numbers.
   The phone numbers should be 10 digits and may have punctuation in them if
   you like; note that Twilio uses the international format `+10005551234`, but
   you should only use 10 digits in the CSV file, not including the country
   code. (We only support US numbers.) For testing purposes, you might want to
   include just your number and maybe another couple if you can get your hands
   on other phones. Save the file.

10. Prepare the group roster. Run `python recreate_database.py FILENAME`, where
    FILENAME is the name of the CSV file you created in step 9. Make sure there
    are no errors and the SQL code generated looks correct.

11. Now actually create the database by pasting or piping this SQL code into
    Postgres on your Heroku instance. You can pipe it like so: `python3
    recreate_database.py FILENAME | heroku pg:psql`. If the list of users
    changes or you’re ready to move from a test list to the real one, you can
    simply update the CSV file and run this again. (Note that all users will
    have their status reset and bus counters will lose their permissions.)

12. Assuming no errors occur in creating the database, the system should be
    ready to go! Try texting `commands` to the number you chose in step 7. If
    all goes well, the app will reply with the commands list. If something goes
    wrong, you can find debug information by typing `heroku logs --tail` (press
    Control-C to stop watching the logs).

13. Grant permissions to your bus counters using the PROMOTE command. The
    superuser can use counter commands without being a bus counter, but will
    not receive notifications that are sent to all bus counters unless he/she
    is explicitly marked as a bus counter.


List of BusBot commands
=======================

*I recommend posting this section on the web somewhere for your users and
updating the URL in the help message in `app.py`.*

All commands are case-insensitive; commands are presented in all-caps in
documentation for clarity.

**Marking your status**

* IN – say you’re on the bus; BusBot replies only on error
* OUT – say you stepped off the bus again for a moment; *BusBot replies on
  success* so you can be certain the bus counters know you’re stepping off. If
  you don’t get a reply, don’t get off the bus without telling someone!
* ABSENT – say you’re not riding the bus and do not need to be accounted for;
  BusBot replies only on error
* WAIT – text the bus counters saying you're not on the bus but are on your
  way; BusBot replies only on error
* STATUS – get your current status, if you’re unsure for whatever reason

**Marking other users’ status**

* MARK [user] AS [IN|OUT|WAIT|ABSENT] – check another user in if they’re unable
  to do so themselves (their phone is dead, say). ‘user’ may be a first name
  (or first and last name if the first name is ambiguous) or phone number. The
  user will get a text informing them that you’ve checked them in.

**Other tools**

* COMMANDS – list available commands (HELP is reserved by an official SMS
  standard)
* WHOIS [user] – show the user’s name, number, status, and special privileges
  if any
* WHOAMI – WHOIS on yourself

**Tools for bus counters only**

* LIST – show how many people are missing (neither on the bus nor absent), or
  their names and statuses if there are fewer than 15 left
* PING – send a reminder text to everyone missing, asking them to check in
* NOTRIDING – show a list of people who have checked themselves out
* RESET – clear information about who's on the bus, to be used upon departure
* HARDRESET – reset and text all users that they need to check in again. Use
  only if you forget to reset at the correct time – texting the whole group is
  obnoxious and can be expensive if the group is large. Note that this will
  take about one second per user to complete due to SMS rate limits.

When the buses leave, one of the counters should RESET (this sends a
notification text to all the counters). Since the system has no notion of time,
if nobody resets the counts, at the next check-in people will be marked as in
when they aren’t, and you might leave without them!

If you forget to reset the counts until people have already started checking
in, you can use HARDRESET to ask everyone to check in again, but this is a pain
for all involved, so it should be avoided whenever possible.


**Tools for the superuser only**

* WALL [message] – send an arbitrary message to every user. This is intended
  for testing that everyone is correctly signed up for the system, or perhaps
  for emergencies. Note that sending messages to (say) 90 users will take 90
  seconds to complete due to SMS rate limits.
* PROMOTE [user] – make user a bus counter
* DEMOTE [user] – what Superuser giveth, Superuser taketh away

The superuser can also use bus counter commands even if not a bus counter.


Tips and notes
==============

* Heroku free tier dynos sleep after 30 minutes of inactivity and take usually
  5-15 seconds to wake up. This is not an issue in terms of functionality –
  just don’t worry if the bot takes a moment to respond to your first text
  after a period of inactivity.
* People usually take a day or two to start remembering to check in. You may be
  able to get them used to it faster by posting a sign in a location visible
  when people get on.
* BusBot is great at pointing out who’s missing and letting you know when
  everyone seems to be around, but people can (and occasionally do!) mark
  themselves as IN when they’re not in fact on the bus. So it’s always wise to
  do a quick head count to double-check when it looks like you’re ready to go.
* Be aware that BusBot does not do any authentication aside from caller ID,
  which can be spoofed. However, the security risks are quite low; an outsider
  would have to guess both BusBot’s number and a number in your user database
  to even use BusBot, and all the intruder could do would be to mess with some
  people’s statuses and maybe obtain their phone numbers.


Suggested improvements
======================

BusBot is complete and functional, but over the course of my recent tour we
thought of a number of useful enhancements that I haven’t had time to
implement. If you feel like playing around with the app a little bit, you might
find some of these useful and I’d love to see pull requests for them:

* Look up what XML is actually supposed to be returned to Twilio upon a
  successful request. Currently I get email warnings every day because BusBot
  is just returning a string; I was pressed for time and couldn’t find the
  documentation on what I was supposed to return. The bot works fine, but
  getting an email every day saying “There were 100 errors today!” is annoying.
* Improve the name parser. If there is no exact match, try suggesting partial
  or close matches. Allow last names only if unambiguous. Allow the first
  initial of the last name to be used to disambiguate people with the same
  first name.
* Add a function that lets someone be marked as “perpetually absent” (they’re
  stepping out of the tour group for a couple of days, say). Such a user should
  be completely ignored for all purposes (except STATUS and WHOIS, perhaps)
  until they’re marked unabsent again. Currently you have to manually delete
  such a user from the database and re-add them later, or remember that they’re
  going to be marked out all the time and maybe end up sending them annoying
  pings.
* Add at least a compile-time option to disallow any user from using WHOIS,
  limiting it to just bus counters. Our group already has a central list of
  phone numbers that anyone can look at, and we find this function very useful,
  but it may be an invasion of privacy for other groups.
* Ping the bus counters if some time has passed since the last person marked
  themselves IN (suggesting that the buses left and nobody reset the counts).
  This is tricky since the app normally responds only to external requests. An
  alternative and perhaps easier option would be to store the time of the last
  request in the database and notify the bus counters if people start marking
  themselves IN more than half an hour after the last mark; this wouldn’t
  completely prevent issues, but it would at least head off major problems.
* Add a command to check your balance on Twilio if you don’t want to use
  auto-refill; going to the web console all the time while you’re on the road
  can get irritating.
* Improve the permissions system so that people other than the superuser
  hard-coded into the app can be allowed to use WALL, PROMOTE, and DEMOTE.
* Allow users to change their own first names if they prefer to be called
  something other than their formal name that you copied into the user
  database.

Using the `testclient.py` script may be a cheaper and easier way to debug than
sending a whole bunch of text messages; see the comments at the top of the file
for how to use it.
