import os 
import couchdb
import uuid
import requests

from datetime import datetime
from flask import Flask, jsonify, session, render_template, request, redirect, g, url_for, flash
# from .models import User
from datetime import datetime
from couchdb.mapping import Document, TextField, DateTimeField, ListField, FloatField, IntegerField, ViewField
from werkzeug.utils import secure_filename
from werkzeug import FileStorage
from flask_uploads import (UploadSet, configure_uploads, IMAGES, UploadNotAllowed)
# from cloudant.view import View

from tokens import generate_confirmation_token, confirm_token
from flask_mail import Mail
from emails import send_email

# UPLOADED_PHOTOS_DEST = 'uploads'
GOOGLE_GEOCODE_URL = 'https://maps.googleapis.com/maps/api/geocode/json?place_id={0}&key={1}'
GOOGLE_API_KEY = 'AIzaSyDVE9osSCgxkIPp4LGEp1xwhmGrMVxNpnc'

GOOGLE_DISTANCE_URL = 'https://maps.googleapis.com/maps/api/distancematrix/json?origins={0},{1}&destinations={2},{3}&key={4}'

cloudant_data = {
    "username": "052ca863-0f20-49a8-9813-330b0813683a-bluemix",
    "password": "68e8bdaa4739229b83095bf31b9c8256d5790022a184e8cdfefec270ea2be740",
    "host": "052ca863-0f20-49a8-9813-330b0813683a-bluemix.cloudant.com",
    "port": '443',
}

DATABASE_URL = "https://052ca863-0f20-49a8-9813-330b0813683a-bluemix.cloudant.com/bazaardata/"

app = Flask(__name__)
app.config.from_object(__name__)
# app.config.from_envvar('DEALBAZAAR_SETTINGS', silent=True)
app.secret_key = os.urandom(24)

mail = Mail(app)
app.config.update(
        DEBUG = True,
        SECURITY_PASSWORD_SALT = 'random',
        BCRYPT_LOG_ROUNDS = 13,
        MAIL_SERVER = 'smtp.gmail.com',
        MAIL_PORT = 587,
        MAIL_USE_TLS = True,
        MAIL_USE_SSL = False,
        MAIL_USERNAME = os.environ['DEALBAZAAR_USERNAME'],
        MAIL_PASSWORD = os.environ['DEALBAZAAR_PASSWORD'],
        MAIL_DEFAULT_SENDER = 'dealbazaar.swe@gmail.com'
    )

mail = Mail(app)
# uploaded_photos = UploadSet('photos', IMAGES)
# configure_uploads(app, uploaded_photos)


class User(Document):
    doc_type = 'user'
    name = TextField()
    email = TextField()
    password = TextField()
    contact = IntegerField()
    college = TextField()
    city = TextField()
    address = TextField()
    confirmed = IntegerField(default=0)
    createdate = DateTimeField(default=datetime.now)
    latitude = TextField()
    longitude = TextField()
    place_id = TextField()

    @classmethod
    def get_user(cls,email):
        db = get_db()
        user = db.get(email,None)

        if user is None:
            return None
        
        return cls.wrap(user)

    def confirm(self):
        db = get_db()
        self.confirmed = 1
        self.store(db)
    
    def calculate_geocode(self):
        place_id = self.place_id
        data = requests.get(GOOGLE_GEOCODE_URL.format(self.place_id, GOOGLE_API_KEY))
        self.latitude = str(data.json()['results'][0]['geometry']['location']['lat'])
        self.longitude = str(data.json()['results'][0]['geometry']['location']['lng'])

    def update(self, contact=None, password=None, city = None, college=None, address=None, placeid=None):
        db = get_db()
        if contact and contact != "":
            self.contact = contact

        if city and city != "":
            self.city = city

        if college and college != "":
            self.college = college

        if password and password != "":
            self.password = password

        if address and address != "" and placeid != "":
            self.address = address
            self.place_id = placeid
            self.calculate_geocode()

        self.store(db)


class Item(Document):
    doc_type = TextField(default='item')
    name = TextField()
    item_type = TextField()
    description = TextField()
    original_price = FloatField()
    mrp = FloatField()
    date = DateTimeField(default=datetime.now)
    user = TextField()
    filename = TextField()
    sold = IntegerField(default=0)

    @classmethod
    def all(cls,db):
        return cls.view(db,'_design/items/_view/all-items')

    def confirmSold(self,id):
        db = get_db()
        self.sold = 1
        self.store(db)

    @classmethod
    def by_date(cls,limit = None):
        db = get_db()
        item_obj = cls.view(
                            db,
                            '_design/items/_view/byDate',
                            descending=True,
                            include_docs=True
                            )
        items = []
        for item in item_obj:
            items.append(cls.wrap(item))

        if limit is not None:
            return items[0:limit]

        return items
    
    @classmethod
    def by_user(cls,email):
        db = get_db()
        item_obj = cls.view(
                            db,
                            '_design/items/_view/byUser',
                            key=email,
                            include_docs=True
                            )
        items = []
        for item in item_obj:
            items.append(cls.wrap(item))

        return items

    @classmethod
    def by_item_type(cls,item_type):
        db = get_db()
        item_obj = cls.view(
                            db,
                            '_design/items/_view/byItemType',
                            key=item_type,
                            include_docs=True
                            )
        items = []
        for item in item_obj:
            items.append(cls.wrap(item))

        return items

    @classmethod
    def by_item_name(cls,name):
        db = get_db()
        item_obj = cls.view(
                            db,
                            '_design/items/_view/byItemName',
                            key=name,
                            include_docs=True
                            )
        items = []
        for item in item_obj:
            items.append(cls.wrap(item))

        return items

    @classmethod
    def get_item(cls,id):
        db = get_db()
        item = db.get(id,None)

        if item is None:
            return None
        
        return cls.wrap(item)

    def calculate_distance(self, customer_id):
        customer = User.get_user(customer_id)
        seller = User.get_user(self.user)

        data = requests.get(GOOGLE_DISTANCE_URL.format(customer.latitude,
                            customer.longitude, seller.latitude,
                            seller.longitude, GOOGLE_API_KEY))

        distance_text = str(data.json()['rows'][0]['elements'][0]['distance']['text'])
        distance_value = int(data.json()['rows'][0]['elements'][0]['distance']['value'])
        time = str(data.json()['rows'][0]['elements'][0]['duration']['text'])

        distance = [distance_text, distance_value, time]

        return distance

class Bid(Document):
    doc_type = TextField(default='bid')
    amount = FloatField()
    user = TextField()
    item = TextField()
    created = DateTimeField()

    @classmethod
    def get_bid(cls,id):
        db = get_db()
        bid = db.get(id,None)

        if bid is None:
            return None
        
        return cls.wrap(bid)
    
    @classmethod
    def get_by_item(cls,db,item_id):
        # print '_design/bids/_view/get-bids'+item_id
        bids = []
        bids_obj = cls.view(
                            db,
                            '_design/bids/_view/get-bids',
                            key=item_id,
                            include_docs=True
                            )
        for row in bids_obj:
            bids.append(cls.wrap(row))
        return bids

class Purchased(Document):
    doc_type = TextField(default='purchase')
    item_id = TextField()
    buyer = TextField()
    seller = TextField()
    date = DateTimeField()

    @classmethod
    def by_user(cls,buyer):
        db = get_db()
        item_obj = cls.view(
                            db,
                            '_design/purchased/_view/get_byUser',
                            key=buyer,
                            include_docs=True
                            )
        items = []
        for item in item_obj:
            items.append(cls.wrap(item))

        return items

def get_db():
    if not hasattr(g, 'db'):
        server = couchdb.Server("https://"+cloudant_data['username']+':'+cloudant_data['password']
          +'@'+cloudant_data['host']+':'+cloudant_data['port'])

        try:
            g.db = server.create('bazaardata')
        except:
            g.db = server['bazaardata']        
    
    return g.db

# @app.teardown_appcontext
# def close_db(error):
#     if hasattr(g, 'db')

@app.before_request
def before_request():
    g.user = None
    if 'user' in session:
        g.user = session['user']


# @app.route('/')
# def Welcome():
#     return render_template('signup.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        user = User()

        form_data = request.form
        print form_data

        if form_data.get('name'):
            user.name = form_data.get('name',None)
        else:
            flash('Name field is required', category = "error")
            return render_template('signup.html')

        if form_data.get('email'):
            email = form_data.get('email',None)
            if User.get_user(email) is None:    
                user.email = email
            else:
                flash("User already exists", category='error')
                return render_template('signup.html')
        else:
            flash('Email field is required', category = "error")
            return render_template('signup.html')

        if form_data.get('password'):
            user.password = form_data.get('password',None)
        else:
            flash('Password field is required', category = "error")
            return render_template('signup.html')

        if form_data.get('contact'):
            if len(form_data.get('contact')) == 10 and int(form_data.get('contact')) > 0:
                user.contact = form_data.get('contact',None)
            else:
                flash('Invalid Mobile Number', category = "error")
                return render_template('signup.html')
        else:
            flash('Contact field is required', category = "error")
            return render_template('signup.html')

        if form_data.get('college'):
            user.college = form_data.get('college',None)
        else:
            flash('College field is required', category = "error")
            return render_template('signup.html')

        if form_data.get('city'):
            user.city = form_data.get('city',None)
        else:
            flash('City field is required', category = "error")
            return render_template('signup.html')

        if form_data.get('address', None):
            user.address = form_data.get('address',None)
        else:
            flash('Address field is required', category = "error")
            return render_template('signup.html')

        # print "place ", form_data.get('placeid')
        user.place_id = form_data.get('placeid')

        # print user

        user.confirmed = 0
        
        user.calculate_geocode()

        db = get_db()
        db[user.email] = user._data

        token = generate_confirmation_token(user.email)
        confirm_url = url_for('confirm_email', token=token, _external=True)
        html = render_template('activate.html', confirm_url=confirm_url)
        subject = "Please confirm your email"
        #print user.email
        send_email(user.email, subject, html)

        flash('A confirmation link is sent to your email_id.Please confirm before logging in.', category = "error")
        return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        session.pop('user', None)

        email = request.form['email']
        # db = get_db()
        
        user = User.get_user(email)

        if user is not None:
            if not user.confirmed:
                flash('Please confirm your account first...!!!', category="error")

            elif request.form['password'] == user.password:
                session['user'] = user._data
                return redirect(url_for('after_login'))
            else:
                flash('Invalid password', category="error")
        else:
            flash('Invalid email', category="error")
        return render_template('login.html')
        # if request.form['password'] == 'password':
        #     session['user'] = request.form['email']
        #     return redirect(url_for('after_login'))

    return render_template('login.html')        

@app.route('/home')
def after_login():
    if g.user:
        recent_items = Item.by_date(4)

        for i in recent_items:
            i.src = DATABASE_URL + i.id + '/' + i.name + '.jpg/'


        return render_template('home1.html', recent_items = recent_items)

    return redirect(url_for('login'))

@app.route('/confirm/<token>') 
def confirm_email(token):
    try:
        # print token
        email = confirm_token(token)
        # print "email ",email
    except:
        flash('The confirmation link is invalid or has expired.', category='error')

    if email:    
        user = User.get_user(email)

        if user.confirmed:
            return 'Account already confirmed. Please login.'
        else:
            user.confirm()
    else:
        flash("Unexpected error", category="error")

    return redirect(url_for('login'))

@app.route('/posted_items')
def posted_items():
    if g.user:
        user_items = Item.by_user(g.user['email'])

        for i in user_items:
            i.src = DATABASE_URL + i.id + '/' + i.name + '.jpg/'
            #print i.src
        recent_items = Item.by_date(4)

        for i in recent_items:
            i.src = DATABASE_URL + i.id + '/' + i.name + '.jpg/' 

        return render_template('posted_items.html', items = user_items, recent_items=recent_items)

    return redirect(url_for('login'))


@app.route('/sell', methods=['GET', 'POST'])
def post_item():
    if g.user:
        if request.method == 'POST':
            item = Item()

            form_data = request.form

            if request.files.get('photo'):
                photo = request.files.get('photo')
            else:
                flash('Image is required', category = "error")
                return render_template('upload1.html')

            if form_data.get('item_name'):
                item.name = form_data.get('item_name',None)
            else:
                flash('Item Name is required', category = "error")
                return render_template('upload1.html')

            if form_data.get('description'):
                if len(form_data.get('description')) > 25 and len(form_data.get('description')) < 251:
                    item.description = form_data.get('description',None)
                else:
                    flash('Description length should be between 25-250 characters.', category = "error")
                    return render_template('upload1.html')
            else:
                flash('Description is required', category = "error")
                return render_template('upload1.html')

            if form_data.get('item_type'):
                item.item_type = form_data.get('item_type', None).lower()
            else:
                flash('Item type is required', category = "error")
                return render_template('upload1.html')

            if int(form_data.get('original_price')) > 0:
                #print "adadad"
                item.original_price = form_data.get('original_price',None)
            else:
                #print "errrrrr"
                flash('Invalid price', category = "error")
                return render_template('upload1.html')

            if int(form_data.get('mrp')) > 0:
                #print "adadad"
                item.mrp = form_data.get('mrp',None)
            else:
                #print "errrrrr"
                flash('Invalid MRP.', category = "error")
                return render_template('upload1.html')

            item.user = g.user.get('email', None)
            #item.date = datetime.datetime.now

            db = get_db()
            # try:
            #     filename = uploaded_photos.save(photo)
            # except UploadNotAllowed:
            #     flash("The upload was not allowed")
            # else:
            #     item.filename = filename

            item.id = uuid.uuid4().hex
            item.store(db)
            db.put_attachment(item,photo,filename=str(item.name)+'.jpg',content_type='image/jpeg')
            
            flash('Your item has been posted.', category = "error")
            return redirect(url_for('after_login'))
        return render_template('upload1.html')
    else:
        return redirect(url_for('login'))

@app.route('/view/', methods=['GET', 'POST'])
def view():
    if g.user:
        if request.method == 'POST':
            query_text = request.form.get('search')

            query_text = query_text.lower()

            item_type_filter = Item.by_item_type(query_text) + Item.by_item_name(query_text)
            
            for i in item_type_filter:
                i.src = DATABASE_URL + i.id + '/' + i.name + '.jpg/'
            print item_type_filter
            recent_items = Item.by_date(4)
            
            for i in recent_items:
                i.src = DATABASE_URL + i.id + '/' + i.name + '.jpg/'

            return render_template('search.html', items = item_type_filter, recent_items=recent_items)
    
        else:    
            db = get_db()
            it = Item.all(db)

            for i in it:
                i.src = DATABASE_URL + i.id + '/' + i.name + '.jpg/'
                #print i.src
            recent_items = Item.by_date(4)

            for i in recent_items:
                i.src = DATABASE_URL + i.id + '/' + i.name + '.jpg/'

            return render_template('search.html', items = it, recent_items=recent_items)
    
    return redirect(url_for('login'))

@app.route('/view/<id>', methods=['GET', 'POST'])
def item_details(id=None):
    if request.method == 'POST':
        owner = Item.get_item(id).user

        if g.user['email'] == owner:
            flash("You cannot place bid for this item.", category='error')
            return redirect('/view/'+id)
        else:
            bid = Bid()

            if int(request.form.get('amount')) > 0:
                bid.amount = request.form.get('amount')
            else:
                flash('Invalid Bid', category = "error")
                return redirect('/view/'+id)

            bid.item = id
            bid.user = g.user['email']

            db = get_db()
            bid.id = uuid.uuid4().hex
            bid.store(db)

            flash('Your bid has been placed successfully..!!!', category='error')
            return redirect('/view/'+id)
    else:
        if(id):
            db = get_db()
            item = Item.get_item(id)
            
            items = item._data
            src = DATABASE_URL + id + '/' + item.name + '.jpg/'
            
            distance = item.calculate_distance(g.user['email'])
            return render_template('item_description.html', item=items, src=src, distance=distance)

@app.route('/view/<id>/bid')
def view_bids(id=None):
    if g.user:
        db = get_db()
        bids = Bid.get_by_item(db,id)

        for bid in bids:
            x = User.get_user(bid.user)
            bid.name = x.name 
    
        item = Item.get_item(id)
            
        items = item._data
        src = DATABASE_URL + id + '/' + item.name + '.jpg/'

        flash('Buyer details have been sent to your emailid.', category='error')
        return render_template('view_bids1.html',bids=bids,src=src,item=items)
    else:
        return redirect(url_for('login'))

@app.route('/view/<id>/bid/<bid_id>/accept', methods=['GET'])
def accept_bid(id=None, bid_id=None):
    if g.user:
        buyer_email = Bid.get_bid(bid_id).user
        seller_email = Item.get_item(id).user
        
        buyer = User.get_user(buyer_email)
        seller = User.get_user(seller_email)

        db = get_db()
        item = Item.get_item(id)
        
        items = item._data
        
        src = DATABASE_URL + id + '/' + item.name + '.jpg/'

        html = render_template('seller.html', name=buyer.name, email=buyer_email, contact=buyer.contact,
                                college=buyer.college, city=buyer.city, address=buyer.address,
                                item=items, src=src )

        subject = "Buyer details"

        send_email(seller_email, subject, html)

        html1 = render_template('buyer.html', name=seller.name, email=seller_email, contact=seller.contact,
                                college=seller.college, city=seller.city, address=seller.address, 
                                item=items, src=src)

        subject1 = "Seller details"

        send_email(buyer_email, subject1, html1)

        item.confirmSold(id)

        purchase = Purchased()
        purchase.buyer = buyer_email
        purchase.item_id = id
        purchase.seller = seller.name
        purchase.date = datetime.now()
        
        db = get_db()
        purchase.id = uuid.uuid4().hex
        purchase.store(db)
        print purchase

        flash("Confirmation Email is sent to your email id.", category='error')
        return redirect(url_for('view_bids', id=id))

    return redirect(url_for('login')) 
         
@app.route('/sold_items')
def sold_items():
    if g.user:
        user_items = Item.by_user(g.user['email'])

        sold_items = []
        for i in user_items:
            if i.sold == 1:
                sold_items.append(i)
         
        for i in sold_items:
            i.src = DATABASE_URL + i.id + '/' + i.name + '.jpg/'

        recent_items = Item.by_date(4)

        for i in recent_items:
            i.src = DATABASE_URL + i.id + '/' + i.name + '.jpg/'

        return render_template('sold_items.html', sold_items = sold_items, recent_items=recent_items)

    return redirect(url_for('login'))

@app.route('/purchased_items')
def purchased_items():
    if g.user:
        purchase = Purchased.by_user(g.user['email'])
        print "purchase",purchase
        if len(purchase)>0:
            purchased_items = []
            if len(purchase) > 0:
                for i in purchase:
                    item_id = i.item_id
                    item = Item.get_item(item_id)
                    if item:
                        item.seller = i.seller
                        item.sold_date = i.date.date()
                        purchased_items.append(item)

            for i in purchased_items:
                i.src = DATABASE_URL + i.id + '/' + i.name + '.jpg/'
            #print purchased_items

            recent_items = Item.by_date(4)

            for i in recent_items:
                i.src = DATABASE_URL + i.id + '/' + i.name + '.jpg/'

            return render_template('purchased_items.html', items = purchased_items, recent_items=recent_items)
        else:
            purchased_items = []

            recent_items = Item.by_date(4)

            for i in recent_items:
                i.src = DATABASE_URL + i.id + '/' + i.name + '.jpg/'

            return render_template('purchased_items.html', items = purchased_items, recent_items=recent_items)
    return redirect(url_for('login'))

@app.route('/views/<filter>', methods=['GET', 'POST'])
def filter_byLocation(filter=None):
    if g.user:
        db = get_db()
        it = Item.all(db)
        items = []
        for i in it:
            i.src = DATABASE_URL + i.id + '/' + i.name + '.jpg/'
            i.distance = i.calculate_distance(g.user['email'])
            items.append(i)
        
        items.sort(key = lambda x : x.distance[1])

        recent_items = Item.by_date(4)

        for i in recent_items:
            i.src = DATABASE_URL + i.id + '/' + i.name + '.jpg/'

        return render_template('search.html', items = items, recent_items=recent_items)

@app.route('/logout', methods=['GET'])
def logout():
    if g.user:
        session.pop('user', None)

    flash('You have been successfully logged out.', category="error")
    return render_template('login.html')

@app.route('/settings', methods=['GET', 'POST'])
def update():
    if g.user:
        if request.method == "POST":
            form_data = request.form
            #print form_data.get('placeid') == ""

            email = g.user.get('email', None)
            user = User.get_user(email)

            #call user update function here
            user.update(form_data.get('contact', None), form_data.get('password', None),
                       form_data.get('city', None), form_data.get('college', None),
                       form_data.get('address', None), form_data.get('placeid', None))

            user_data = {}
            user_data['name'] = user.name
            user_data['email'] = user.email
            user_data['city'] = user.city
            user_data['college'] = user.college
            user_data['address'] = user.address
            user_data['contact'] = user.contact

            flash("Account details have been updated.", category="error")
            return render_template('profile.html', data = user_data)
        else:
            email = g.user.get('email', None)
            user = User.get_user(email)
            user_data = {}
            user_data['name'] = user.name
            user_data['email'] = user.email
            user_data['city'] = user.city
            user_data['college'] = user.college
            user_data['address'] = user.address
            user_data['contact'] = user.contact
            return render_template('profile.html' , data = user_data)


    else:
        return redirect(url_for('login'))

port = os.getenv('PORT', '5000')
if __name__ == "__main__":
	app.run(host='0.0.0.0', port=int(port), debug=True)
