from .core_requests import get_station_data, get_endorsements, get_logins, get_roster, required_courses
from .discord import send_message
from .helpers import split_compare


ratings = {
    1: 'OBS',
    2: 'S1',
    3: 'S2',
    4: 'S3',
    5: 'C1'
}


required_rating = {
    'DEL': 2,
    'GND': 2,
    'TWR': 3,
    'APP': 4,
    'DEP': 4,
    'CTR': 5
}


def safe_get(data: dict, key: str) -> object:
    if key in data.keys():
        return data[key]
    else:
        return False


def check_obs_and_primary(connection: dict) -> bool:
    """
    Checks if the connection needs to be checked, i.e. not observer and primary set
    """
    return connection['facility'] != 0 and connection['frequency'] != '199.998'


def output_dict(may_control: bool, discord_msg: str, website_msg: str, required_courses: list[dict] = []) -> dict:
    output = {
        'may_control': may_control,
        'discord_msg': discord_msg,
        'website_msg': website_msg,
        'required_courses': required_courses
    }
    return output


def check_connection(connection: dict, station_data: list[dict], solos: list[dict], t1: list[dict], t2: list[dict],
                     roster: list[dict]) -> dict:
    # Filter out EDW
    if connection['callsign'] in ['EDW_TWR', 'EDW_APP']:
        return output_dict(True, 'EDW', 'EDW')

    user_has_solo = False
    user_has_t1 = False
    station_is_t1 = False

    # Check whether controller is on roster
    if connection['cid'] not in roster:
        return output_dict(False,
                           f'{connection["cid"], connection["name"]} controlling {connection["callsign"]} not on roster.',
                           'You may not control this station as you are not on the roster.')

    if connection['frequency'] == 'website':
        # If function called from website, match station by login
        data = [station for station in station_data if station['logon'] == connection['callsign']]
    else:
        # Match station by first four letters of callsign (FIR) and primary frequency
        data = [station for station in station_data if station['logon'][:4] == connection['callsign'][:4] and station['frequency'] == connection['frequency']]

    # Check whether station was found
    if data:
        data = data[0]
    else:
        return output_dict(False,
                           f'No station found {connection["callsign"], connection["cid"], connection["name"]}',
                           'Station not found')

    # Rating check
    station_type = data['logon'].split('_')[-1]
    if required_rating[station_type] > connection['rating']:
        # Check for solo endorsement
        # Get all solo endorsements of user
        user_solos = [solo for solo in solos if solo['user_cid'] == connection['cid']]
        if user_solos:
            user_has_solo = split_compare(user_solos[0]['position'], data['logon'])
        elif station_type == 'TWR':
            # Is TWR part of T1 Program?
            if not safe_get(data, 's1_twr') and connection['rating'] == 2:
                return output_dict(False,
                                   f'{connection["cid"], connection["name"]} controlling TWR {connection["callsign"]} not in S1 TWR Program.',
                                   'This TWR may not be controlled with S1.')
        else:
            return output_dict(False,
                               f'{connection["cid"], connection["name"]} controlling station {connection["callsign"]} without rating or solo.',
                               'You need a higher rating to control this position.')

    # Check for required courses
    courses = required_courses(data['logon'], connection['cid'])
    if courses:
        return output_dict(False,
                           f'{connection["cid"], connection["name"]} controlling station '
                           f'{connection["callsign"]} without required Moodle courses.',
                           'Before you control, you need to pass the following courses:', required_courses=courses)

    # Restricted station check
    if safe_get(data, 'gcap_status') == 'AFIS':
        user_endorsement = [endorsement for endorsement in t2 if endorsement['user_cid'] == connection['cid'] and endorsement['position'] == 'EDXX_AFIS']
        if not user_endorsement:
            return output_dict(False,
                               f'{connection["cid"], connection["name"]} has no AFIS endorsement for {connection["callsign"]}.',
                               'You need an AFIS endorsement to control this position.')
    elif safe_get(data, 'gcap_status') == '1':
        station_is_t1 = True
        user_endorsements = [endorsement for endorsement in t1 if endorsement['user_cid'] == connection['cid']]
        user_has_t1 = False
        for endorsement in user_endorsements:
            if station_type in ['DEL', 'GND']:
                # Endorsements for DEL and GND are combined as 'GNDDEL', thus need to replace both _GND and _DEL with _GNDDEL
                if split_compare(endorsement['position'], data['logon'].replace("_GND", "_GNDDEL").replace("_DEL", "_GNDDEL")):
                    user_has_t1 = True
                    break
            elif station_type in ['TWR', 'APP', 'DEP']:
                if split_compare(endorsement['position'], data['logon']):
                    user_has_t1 = True
                    break
            else:
                # For center, endorsement must match exactly
                if endorsement['position'] == data['logon']:
                    user_has_t1 = True
                    break
    if station_is_t1:
        if user_has_t1 or user_has_solo:
            return output_dict(True, '', f'You may control {connection["callsign"]}.')
        else:
            return output_dict(False,
                               f'{connection["cid"], connection["name"]} has neither solo nor tier 1 endorsement for {connection["callsign"]}.',
                               'You need an endorsement for this station.')
    else:
        return output_dict(True, '', f'You may control {data["logon"]}.')


if __name__ == '__main__':
    solos = get_endorsements('solo')
    t1 = get_endorsements('tier-1')
    t2 = get_endorsements('tier-2')
    roster = get_roster()
    logins = get_logins()
    datahub = get_station_data()
    for login in logins:
        if check_obs_and_primary(login):
            out = check_connection(login, datahub, solos, t1, t2, roster)
            check, msg = out['may_control'], out['discord_msg']
        if not check:
            with open('/data/monitor/messaged.txt', 'r') as f:
                content = f.read()
            if not str(login['cid']) in content:
                send_message(msg)
                with open('/data/monitor/messaged.txt', 'a') as f:
                    f.write(str(login['cid']) + '\n')
