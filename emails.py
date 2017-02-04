from flask_mail import Message


def send_email(to, subject, template):
    from welcome import app, mail
    print "send"
    print app.config['MAIL_DEFAULT_SENDER']
    print app.config['MAIL_USERNAME']
    msg = Message(
        subject,
        recipients=[to],
        html=template,
        sender=app.config['MAIL_DEFAULT_SENDER']
    )
    mail.send(msg)