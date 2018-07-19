from google.appengine.ext import ndb
from google.appengine.ext.ndb import msgprop
from protorpc import messages

class TransactionType(messages.Enum):
    DEPOSIT = 0
    WITHDRAWAL = 1
    TRANSFER_IN = 2
    TRANSFER_OUT = 3

class Transaction(ndb.Model):
    type = msgprop.EnumProperty(TransactionType, required = True)
    amount = ndb.FloatProperty(required = True)
    timestamp = ndb.DateTimeProperty(auto_now_add = True)
    other_user_name = ndb.StringProperty() # User that received or sent transfer.

class User(ndb.Model):
    email = ndb.StringProperty(required = True)
    first_name = ndb.StringProperty()
    last_name = ndb.StringProperty()
    balance = ndb.FloatProperty(default = 0)
    transactions = ndb.KeyProperty(Transaction, repeated = True)
