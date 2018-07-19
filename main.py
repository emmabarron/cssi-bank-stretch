import jinja2
import os
import webapp2
from datetime import date, datetime
from google.appengine.api import users
from google.appengine.ext import ndb
from models import User, Transaction, TransactionType
from operator import attrgetter

jinja_current_directory = jinja2.Environment(
    loader = jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions = ['jinja2.ext.autoescape'],
    autoescape = False)

"""
Reads transactions for the given user from the database, then creates a string
of html for adding transactions to the page. If used, the Jinja environment must
be configured to disable autoescaping. If a pending_transaction is provided, it
is assumed that this is being called directly after that transaction was put in
the database and it won't be available in the read. The pending_transaction is
prepended to the list read from database.
"""
def build_transactions_html(user, pending_transaction = None):
    transactions_html = ""
    all_transactions = []

    if pending_transaction:
        all_transactions.append(pending_transaction)

    for transaction_key in user.transactions:
        transactions_from_key = Transaction.query(Transaction.key == transaction_key).fetch()
        if len(transactions_from_key) > 0:
            transaction_from_key = transactions_from_key[0]
            if not pending_transaction or \
                    transaction_from_key.timestamp != pending_transaction.timestamp:
                all_transactions.append(transaction_from_key)
        else:
            print "User has transaction key that doesn't exist in Transactions table: " + str(transaction_key)

    all_transactions.sort(key = attrgetter('timestamp'), reverse = True)

    for transaction in all_transactions:
        timestampString = ""
        if transaction.timestamp.year == date.today().year:
            timestampString = transaction.timestamp.strftime("%b %-d, %-I:%M %p")
        else:
            timestampString = transaction.timestamp.strftime("%b %-d, %Y, %-I:%M %p")

        amount_string = "${:,.2f}".format(abs(transaction.amount))
        if transaction.type == TransactionType.WITHDRAWAL or \
                transaction.type == TransactionType.TRANSFER_OUT:
            amount_string = "-" + amount_string

        transfer_string = ""
        if transaction.type == TransactionType.TRANSFER_OUT:
            transfer_string = "to " + transaction.other_user_name
        elif transaction.type == TransactionType.TRANSFER_IN:
            transfer_string = "from " + transaction.other_user_name

        transactions_html += \
            """
              <div class="transaction">
                <label>{timestamp}</label>
                <label>{amount}</label>
                <label>{other_account}</label>
              </div>
            """.format(
                timestamp = timestampString,
                amount = amount_string,
                other_account = transfer_string
            )

    return transactions_html

"""
Checks that there is a logged in user and that said user has a User entry in the
database. If either is false, uses the request_handler to redirect to login
page. Returns the database User entry otherwise.
"""
def get_logged_in_user(request_handler):
    user = users.get_current_user()
    if not user:
        template_dict = {
            "login_url": users.create_login_url('/')
        }
        login_template = jinja_current_directory.get_template('templates/login.html')
        request_handler.response.write(login_template.render(template_dict))
        print 'transaction stopped because user is not logged in'
        return None

    existing_user = User.get_by_id(user.user_id())

    if not existing_user:
        print 'transaction stopped because user is not in DB'
        request_handler.error(500)
        return None

    return existing_user

"""
Updates the Transaction table and the User table based on the given information.
If a request handler is provided, also sends an updated account home page.
"""
def process_new_transaction(user, new_transaction, request_handler = None):
    new_transaction.put()

    amount = new_transaction.amount
    if new_transaction.type == TransactionType.WITHDRAWAL or \
            new_transaction.type == TransactionType.TRANSFER_OUT:
        amount *= -1
    user.transactions.append(new_transaction.key)
    user.balance += amount
    user.put()

    if request_handler:
        send_account_page(request_handler, user, new_transaction)

"""
Parses the amount string to see if it is a valid float. If it is, returns the
float value.
"""
def process_amount(amount_string):
    try:
        amount = float(amount_string)
    except:
        print 'transaction stopped because error getting float amount'
        return None
    if amount == 0:
        return None

    return amount

"""
Builds the account home page using the given information and sends it using the
given request_handler.
"""
def send_account_page(request_handler, user, pending_transaction = None, error_message = ""):
    balance_string = "${:,.2f}".format(abs(user.balance))
    if user.balance < 0:
        balance_string = "-" + balance_string

    template_dict = {
        "home_message": "Welcome, %s" % user.first_name,
        "transactions_html": build_transactions_html(user, pending_transaction),
        "logout_url": users.create_logout_url('/'),
        "balance": balance_string,
        "transaction_error": error_message,
    }
    account_home_template = jinja_current_directory.get_template('templates/account_home.html')
    request_handler.response.write(account_home_template.render(template_dict))

"""
If there is no authenticated user, send them to the authentication page. If the
user doesn't have a bank account yet, send them to the signin page. Otherwise,
send them to the account home page.
"""
class MainHandler(webapp2.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if user:
            existing_user = User.get_by_id(user.user_id())
            print "existing_user found: " + str(existing_user)

            if existing_user:
                send_account_page(self, existing_user)

            else:
                template_dict = {
                    "logout_url": users.create_logout_url('/')
                }
                signup_template = jinja_current_directory.get_template('templates/signup.html')
                self.response.write(signup_template.render(template_dict))

        else:
            template_dict = {
                "login_url": users.create_login_url('/')
            }
            login_template = jinja_current_directory.get_template('templates/login.html')
            self.response.write(login_template.render(template_dict))

    def post(self):
        if self.request.get("type") == "deposit":
            self.doDeposit()
            return
        elif self.request.get("type") == "withdraw":
            self.doWithdrawal()
            return
        elif self.request.get("type") == "transfer":
            self.doTransfer()
            return

        user = users.get_current_user()
        if not user:
            # Should not be able to get here without being logged in.
            self.error(500)
            return

        new_user = User(
            email = user.email().lower(),
            first_name = self.request.get('first_name'),
            last_name = self.request.get('last_name'),
            id = user.user_id()
        )
        new_user.put()

        send_account_page(self, new_user)

    def doDeposit(self):
        existing_user = get_logged_in_user(self);
        if existing_user == None:
            print 'transaction stopped because user is not logged in'
            return

        amount = process_amount(self.request.get("deposit_amount"))
        if not amount:
            send_account_page(self, existing_user, error_message = "Invalid transaction details")
            return

        new_transaction = Transaction(type = TransactionType.DEPOSIT, amount = amount)
        process_new_transaction(existing_user, new_transaction, self)
        self.redirect('/')

    def doWithdrawal(self):
        existing_user = get_logged_in_user(self);
        if existing_user == None:
            return

        amount = process_amount(self.request.get("withdraw_amount"))
        if not amount:
            send_account_page(self, existing_user, error_message = "Invalid transaction details")
            return

        if amount > existing_user.balance:
            send_account_page(self, existing_user, error_message = "Insufficient funds")
            return

        new_transaction = Transaction(type = TransactionType.WITHDRAWAL, amount = amount)
        process_new_transaction(existing_user, new_transaction, self)

    def doTransfer(self):
        existing_user = get_logged_in_user(self);
        if existing_user == None:
            return

        amount = process_amount(self.request.get("transfer_amount"))
        if not amount:
            send_account_page(self, existing_user, error_message = "Invalid transaction details")
            return

        if amount > existing_user.balance:
            send_account_page(self, existing_user, error_message = "Insufficient funds")
            return

        recipient_email = self.request.get("recipient")
        recipient_users_found = User.query(User.email == recipient_email).fetch()
        if len(recipient_users_found) == 0:
            send_account_page(self, existing_user, error_message = "Recipient has no bank account")
            return
        recipient_user = recipient_users_found[0]

        new_transaction = Transaction(
            type = TransactionType.TRANSFER_OUT,
            amount = amount,
            other_user_name = recipient_user.first_name
        )
        process_new_transaction(existing_user, new_transaction, self)

        recipient_transaction = Transaction(
            type = TransactionType.TRANSFER_IN,
            amount = amount,
            other_user_name = existing_user.first_name
        )
        process_new_transaction(recipient_user, recipient_transaction)


app = webapp2.WSGIApplication([
    ('/', MainHandler),
], debug=True)
