# -*- coding: utf-8 -*-
import smtplib
from email.mime.text import MIMEText
import socket

class Mailer(object):

    def __init__(self, server, port, timeout, user, password, sender, recipients):
        self._user = user
        self._password = password
        self._recipients = recipients
        self._sender = sender
        self._server = server
        self._port = port
        self._success = False
        self._connection = smtplib.SMTP(timeout=timeout)

    def send(self, subject, body):
        msg = MIMEText(body)
        msg["To"] = " ".join(self._recipients)
        msg["From"] = self._sender
        msg["Subject"] = subject
        self._success = False

        try:
            self._connection.connect(self._server, self._port)
        except socket.timeout:
            return


        try:
            self._connection.ehlo()

            # if we can encrypt this session, do it
            if self._connection.has_extn('STARTTLS'):
                self._connection.starttls()
                self._connection.ehlo()

            self._connection.login(self._user, self._password)
            self._connection.sendmail(self._sender, self._recipients, msg.as_string())
            self._success = True
        finally:
            self._connection.quit()

        print self._success

    def get_success(self):
        return self._success

