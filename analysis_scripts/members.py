import json

import pandas as pd
import datetime

from analysis_scripts.forms import get_forms
from analysis_scripts.util import query

FORMATION_DATE = datetime.date(2018, 4, 1)


def extract_primary_email(row):
    emails = row['email_addresses']
    for email in emails:
        if email['primary']:
            return email['address']


def extract_primary_locality(row):
    addresses = row['postal_addresses']
    for address in addresses:
        if address['primary']:
            if 'locality' in address.keys():
                return address['locality']
            elif 'region' in address.keys():
                return address['region']
            else:
                return


def extract_primary_postal_code(row):
    addresses = row['postal_addresses']
    for address in addresses:
        if address['primary']:
            return address['postal_code']


def to_str(row, col):
    return str(row[col])


def extract_signup_form(submissions):
    if len(submissions['_embedded']['osdi:submissions']) < 1:
        return None, None
    signup_submission = submissions['_embedded']['osdi:submissions'][0]
    form_id = signup_submission['action_network:form_id']
    if 'action_network:referrer_data' in signup_submission.keys():
        return form_id, signup_submission['action_network:referrer_data']['source']
    return form_id, None


def get_sign_up_channel(member):
    submissions = query(url=member['_links']['osdi:submissions']['href'])
    return extract_signup_form(submissions)


def extract_data(member):
    try:
        local_group = member['custom_fields']['local_group']
    except KeyError:
        local_group = None
    if local_group == 'Not selected' or local_group == 'No group nearby':
        local_group = None
    sign_up_datetime = member['created_date']
    sign_up_date = sign_up_datetime.split('T')[0]
    sign_up_form, sign_up_website = get_sign_up_channel(member)
    return {'local_group': local_group, 'sign_up_date': sign_up_date, 'sign_up_form': sign_up_form,
            'sign_up_website': sign_up_website}


def map_signup_form(row, form_mapping):
    signup_form = 'Other'

    if row['sign_up_form'] is None or row['sign_up_form'] not in form_mapping.keys():
        return signup_form

    return form_mapping[row['sign_up_form']]


def map_sign_up_channel(row):
    if 'NVDA' in row['form_name']:
        return 'NVDA'

    if 'Volunteer' in row['form_name']:
        return 'Volunteer'

    if 'Join' in row['form_name']:
        if row['has_website'] and row['sign_up_date'] < datetime.date(2020, 2, 20):
            return 'Website'
        return 'HfX Talk'

    if 'Website' in row['form_name']:
        return 'Website'

    return 'Other'


def get_member_stats(backup_file_path, start_date):
    with open(backup_file_path) as f:
        members = json.load(f)['members']

    members_processed = []
    for m in members[0:-1]:
        print(f'Processing {len(members_processed)} of {len(members)}')
        if pd.to_datetime(m['created_date'].split('T')[0]).date() <= start_date:
            continue
        members_processed.append(extract_data(m))

    df = pd.DataFrame(members_processed)

    df['sign_up_date'] = pd.to_datetime(df['sign_up_date']).dt.date
    form_mapping = get_forms().set_index('identifier')['name']
    df['form_name'] = df.apply(map_signup_form, form_mapping=form_mapping, axis=1)
    df['has_website'] = (~df['sign_up_website'].isin(['none', None]))
    df['sign_up_channel'] = df.apply(map_sign_up_channel, axis=1)
    df.loc[df['sign_up_date'] < FORMATION_DATE, 'sign_up_date'] = pd.NaT

    return df


def export_member_stats(backup_file_path, start_date, export_filename='members.csv'):
    """
    Compiles and saves member stats
    To update local groups stats google spreadsheet run this and append output to the hidden raw member data sheet
    (View > hidden sheets), then (File > Import > Upload > Append to current sheet)
    Afterwards, hide the raw member data sheet (right click sheet > Hide sheet)
    Sheet URL: https://docs.google.com/spreadsheets/d/1LrSjkBQqZsIzGKs25O7FC9pHFoOEeRuAAs3IL1NEE8g/edit#gid=709383388

    :param backup_file_path: file path to backup file (generated by backup_script.py in rebel_backup repo)
    :param start_date: only members that signed up after this date are exported
    :param export_filename: filename of exported csv file
    """
    df = get_member_stats(backup_file_path, start_date)
    df_formatted = df[['local_group', 'sign_up_date', 'sign_up_channel']].set_index('sign_up_date')
    df_formatted.to_csv(export_filename)