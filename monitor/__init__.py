from flask import Flask, render_template, request
from .core_requests import get_endorsements, get_roster, get_logins, get_station_data, get_rating, is_course_required
from .monitor_login import check_connection


def create_app():
    app = Flask(__name__, instance_relative_config=True)

    @app.route('/', methods=('GET', 'POST'))
    def main():
        if request.method == 'POST':
            # Check whether ID exists
            try:
                rating = get_rating(int(request.form['cid']))
            except:
                rating = False
                may_control, msg = False, 'The controller ID seems to be incorrect.'
            if rating:
                solos = get_endorsements('solo')
                t1 = get_endorsements('tier-1')
                t2 = get_endorsements('tier-2')
                roster = get_roster()
                datahub = get_station_data()
                connection = {
                    'cid': int(request.form['cid']),
                    'callsign': request.form['station'].upper(),
                    'name': '',
                    'rating': rating,
                    'facility': 5,
                    'frequency': 'website'
                }
                may_control, _, msg = check_connection(connection, datahub, solos, t1, t2, roster)
            course_required = is_course_required(request.form['station'])
            return render_template('main.html', request=request, may_control=may_control, msg=msg, course_required=course_required)
        else:
            return render_template('main.html', request=request)

    return app
