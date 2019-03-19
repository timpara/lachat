import os

from flask import Flask, render_template, request, jsonify,url_for, redirect, flash, request, url_for, redirect, session
from flask_socketio import SocketIO, emit, join_room, leave_room
import json

from functools import wraps
from passlib.hash import sha256_crypt
from MySQLdb import escape_string as thwart
import gc
import datetime

from dbconnect import *

from wtforms import Form, FloatField,BooleanField, StringField, PasswordField, SelectField, IntegerField, validators, RadioField, \
    FormField, FieldList

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
socketio = SocketIO(app)



class RegistrationForm(Form):
    username = StringField('Username', [validators.Length(min=4, max=20), validators.DataRequired()])
    email = StringField('Email address', [validators.Length(min=6, max=50), validators.DataRequired()])

    password = PasswordField('Password', [
        validators.DataRequired(),
        validators.EqualTo('confirm', message='Passwords must be equal.')
    ])
    confirm = PasswordField('Repeat password')


    accept_tos = BooleanField(
        u'I read and accept the TOS',
        [validators.DataRequired()])

def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            flash("You need to login first")
            return redirect(url_for('login_page'))

    return wrap




# Channel Data Global Variables
channel_list = {"general": [] }
present_channel = {"initial":"general"}

@app.route("/logout/")
@login_required
def logout():
    session.clear()
    flash("Bye bye!")
    gc.collect()
    return redirect(url_for('dashboard'))
@app.route('/register/', methods=["GET","POST"])
def register_page():
    try:
        form = RegistrationForm(request.form)
        

        if request.method == "POST" and form.validate():
            username  = form.username.data
            email = form.email.data
            password = sha256_crypt.encrypt((str(form.password.data)))
            c_user_data, conn_user_data = user_data()

            x = c_user_data.execute("SELECT * FROM user_data WHERE username = (%s)", [(thwart(username))])
            if int(x) > 0:
                flash("The username is already taken!")
                return render_template('register.html', form=form)

            else:

                c_user_data.execute("INSERT INTO user_data (username, password, email, tracking,timestamp_reg) VALUES (%s, %s, %s, %s ,%s)",
                          (thwart(username), thwart(password), thwart(email), thwart("/dashboard/"), datetime.datetime.utcnow()))
                conn_user_data.commit()
                c_user_data.close()
                conn_user_data.close()
                gc.collect()





                session['logged_in'] = True
                session['username'] = username
                flash("The registration was successful.")
                return redirect(url_for('dashboard'))

        return render_template("register.html", form=form,header_4="active")

    except Exception as e:
        return(str(e))
@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html")

@app.route('/')
def homepage():
    return render_template("main.html",header_1="active")

@app.route('/login/', methods=["GET","POST"])
def login_page():
    error = ''
    try:
        c, conn = user_data()
        if request.method == "POST":

            c.execute("SELECT password FROM user_data WHERE username = (%s)", [(thwart(request.form['username']))])

            if sha256_crypt.verify(request.form['password'], c.fetchone()[0]):
                session['logged_in'] = True
                session['username'] = request.form['username']

                flash("You are logged in.")
                return redirect(url_for("dashboard"))

            else:
                error = "Invalid login data, please try again."
        c.close()
        conn.close()
        gc.collect()

        return render_template("login.html", error=error,header_3="active")

    except Exception as e:
        flash(e)
        error = e#"Ungueltige Zugangsdaten, versuchen Sie es erneut."
        return render_template("login.html", error=error)

@app.route("/lachat/", methods=["POST", "GET"])
def index():
    if request.method == "GET":
        # Pass channel list to, and use jinja to display already created channels
        return render_template("index.html", channel_list=channel_list)

    elif request.method == "POST":
        channel = request.form.get("channel_name")
        user = request.form.get("username")

        # Adding a new channel
        if channel and (channel not in channel_list):
            channel_list[channel] = []
            return jsonify({"success": True})
        # Switching to a different channel
        elif channel in channel_list:
            # send channel specific data to client i.e. messages, who sent them, and when they were sent
            # send via JSON response and then render with JS
            print(f"Switch to {channel}")
            present_channel[user] = channel
            channel_data = channel_list[present_channel[user]]
            return jsonify(channel_data)
        else:
            return jsonify({"success": False})
@app.route('/dashboard/')
def dashboard():
    return render_template("dashboard.html",header_5="active")

@socketio.on("create channel")
def create_channel(new_channel):
    emit("new channel", new_channel, broadcast=True)

@socketio.on("send message")
def send_message(message_data):
    channel = message_data["current_channel"]
    channel_message_count = len(channel_list[channel])
    del message_data["current_channel"]
    channel_list[channel].append(message_data)
    message_data["deleted_message"] = False
    if(channel_message_count >= 100):
        del channel_list[channel][0]
        message_data["deleted_message"] = True
    emit("recieve message", message_data, broadcast=True, room=channel)

@socketio.on("delete channel")
def delete_channel(message_data):
    channel = message_data["current_channel"]
    user = message_data["user"]
    present_channel[user] = "general"
    del message_data["current_channel"]
    del channel_list[channel]
    channel_list["general"].append(message_data)
    message_data = {"data": channel_list["general"], "deleted_channel": channel}
    emit("announce channel deletion", message_data, broadcast=True)

@socketio.on("leave")
def on_leave(room_to_leave):
    print("Leaving room")
    leave_room(room_to_leave)
    emit("Leave channel ack", room=room_to_leave)

@socketio.on("join")
def on_join(room_to_join):
    print("Joining room")
    join_room(room_to_join)
    emit("Join channel ack", room=room_to_join)
