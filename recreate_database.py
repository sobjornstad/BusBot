#!/usr/bin/env python3
"""
Output SQL code to add the users listed in a CSV file to BusBot's database.
See the setup instructions in the README for more information.

NOTE: This script is SQL injection vulnerable. Never run it on unverified CSV
input, and check the output before piping it into the database!
"""

import string
import sys

if len(sys.argv) < 2:
    print("Usage: python recreate_database.py ROSTER_FILENAME")
    sys.exit(1)

roster = sys.argv[1]

insert_statements = []
with open(roster, 'r') as f:
    for user in f:
        firstname, lastname, phone = (i.strip() for i in user.split(','))
        phone = "+1" + "".join(i for i in phone if i not in string.punctuation)
        assert len(phone) == 12, "Phone number %s invalid" % phone
        insert_statements.append("INSERT INTO users (iscounter, firstname, lastname, phone, curstatus) VALUES (false, '%s', '%s', '%s', 'UNSET');" % (firstname, lastname, phone))

print("BEGIN TRANSACTION;")
print("DROP TABLE users;")
print("DROP TABLE status;")
print("CREATE TABLE users (uid serial PRIMARY KEY, iscounter BOOLEAN, firstname VARCHAR, lastname VARCHAR, phone VARCHAR, curstatus VARCHAR);")
print("CREATE TABLE status (uid serial PRIMARY KEY, all_in BOOLEAN);")
print("INSERT INTO status (all_in) VALUES (false);")
print("\n".join(insert_statements))
print("COMMIT;")
