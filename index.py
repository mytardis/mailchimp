import sys
import os
from datetime import datetime, timedelta
import hashlib
import argparse
import yaml
import re

from psycopg2 import connect, sql
from psycopg2.extras import RealDictCursor

import mailchimp_marketing as MailchimpMarketing
from mailchimp_marketing.api_client import ApiClientError


def get_parser():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--config",
        default="settings.yaml",
        help="Config file location (default: settings.yaml)."
    )

    parser.add_argument(
        "--days",
        type=int,
        default=0,
        help="Populate past days of data."
    )

    return parser


def get_mc_members(list_id, segment_id):
    batch = 100
    results = batch
    members = []

    while batch == results:
        rsp = client.lists.get_segment_members_list(
            list_id,
            segment_id,
            count=batch,
            offset=len(members))
        results = len(rsp["members"])
        for member in rsp["members"]:
            members.append(member["email_address"].lower())

    return sorted(members)


def get_db_users(cur, days, exclude):
    filters = [
        sql.SQL("u.is_active = True"),
        sql.SQL("a.approved = True")
    ]

    if days != 0:
        rewind = datetime.now() + timedelta(-days)
        filters.append(
            sql.SQL("u.last_login >= '{}'".format(rewind.date()))
        )

    q = sql.SQL("""
        SELECT
            LOWER(u.email) AS email_address,
            u.first_name,
            u.last_name
        FROM auth_user AS u
        LEFT JOIN tardis_portal_userprofile AS p
        ON p.user_id = u.id
        LEFT JOIN tardis_portal_userauthentication AS a
        ON a.userProfile_id = p.id
        WHERE {}
        ORDER BY LOWER(u.email)
    """).format(sql.SQL(" AND ").join(filters))

    cur.execute(q)
    rows = cur.fetchall()

    exc = []
    for pattern in exclude:
        exc.append(re.compile(pattern))

    users = []
    dups = []
    for row in rows:
        email = row["email_address"].strip()
        if len(email) and email not in dups:
            keep = True
            for e in exc:
                if bool(re.search(e, email)):
                    keep = False
                    break
            if keep:
                dups.append(email)
                users.append({
                    "email_address": email,
                    "first_name": row["first_name"].strip(),
                    "last_name": row["last_name"].strip()
                })

    return users


args = get_parser().parse_args()

if os.path.isfile(args.config):
    with open(args.config) as f:
        settings = yaml.load(f, Loader=yaml.Loader)
else:
    sys.exit("Can't find settings.")

try:
    print("Checking Mailchimp API...")
    client = MailchimpMarketing.Client()
    client.set_config({
        "api_key": settings["mailchimp"]["api_key"]
    })
    rsp = client.ping.get()
except ApiClientError as e:
    sys.exit("Can't ping Mailchimp API - {}.".format(str(e)))

try:
    print("Connecting to the database...")
    con = connect(
        host=settings["database"]["host"],
        port=settings["database"]["port"],
        user=settings["database"]["username"],
        password=settings["database"]["password"],
        database=settings["database"]["database"]
    )
except Exception as e:
    sys.exit("Can't connect to the database - {}.".format(str(e)))

cur = con.cursor(cursor_factory=RealDictCursor)

print("Reading database...")
users = get_db_users(cur, args.days, settings["exclude"])
print("The list has %s emails." % len(users))

print("Closing connection to the database...")
cur.close()
con.close()

print("Reading list members...")
mailchimp_emails = get_mc_members(
    settings["mailchimp"]["list_id"],
    settings["mailchimp"]["segment_id"])
print("The list has %s emails." % len(mailchimp_emails))

print("Sync...")

for user in users:
    email = user["email_address"]
    if email not in mailchimp_emails:
        try:
            client.lists.get_list_member(
                settings["mailchimp"]["list_id"],
                hashlib.md5(email.encode("utf-8")).hexdigest())
        except ApiClientError:
            print("Adding %s to the list" % email)
            client.lists.add_list_member(
                settings["mailchimp"]["list_id"],
                {
                    "email_address": email,
                    "status": "subscribed",
                    "merge_fields": {
                        "FNAME": user["first_name"].strip(),
                        "LNAME": user["last_name"].strip()
                    }
                })
        print("Adding %s to the segment" % email)
        rsp = client.lists.create_segment_member(
            settings["mailchimp"]["list_id"],
            settings["mailchimp"]["segment_id"],
            {
                "email_address": email
            })
    else:
        mailchimp_emails.remove(email)

for email in mailchimp_emails:
    print("Removing %s from the segment" % email)
    client.lists.remove_segment_member(
        settings["mailchimp"]["list_id"],
        settings["mailchimp"]["segment_id"],
        hashlib.md5(email.encode("utf-8")).hexdigest())

print("Completed.")
