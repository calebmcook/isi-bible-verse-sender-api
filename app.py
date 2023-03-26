import os
import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from flask import Flask, jsonify, make_response, request, abort
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse
import logging

logger = logging.getLogger(__name__)
app = Flask(__name__)

USERS_TABLE = os.environ['USERS_TABLE']

#get twilio auth token from AWS systems manager parameter store
client = boto3.client('ssm')
response = client.get_parameter(
    Name='/twilio/garretson_technology_isi_subaccount/twilio_auth_token',
    WithDecryption=True
)
TWILIO_AUTH_TOKEN = response['Parameter']['Value']

@app.route('/users', methods=['POST'])
def create_user():
    #validate that the request originates from Twilio
    validator = RequestValidator(TWILIO_AUTH_TOKEN)
    if not validator.validate(request.url, request.form, request.headers.get('X-Twilio-Signature')):
        abort(400)

    #pull data from request
    current_status = str.upper(request.form['Body'])
    phone_number = request.form['From']

    #response logic
    if current_status == 'DAILY-SMS':
        msg = 'Thank you for your interest in the ISI daily bible verse service! You are now subscribed to the MMS sent at 7am AZ time. Text "STOP-SERVICES" any time to cancel your subscription.'
    elif current_status == 'DAILY-IMAGE':
        msg = 'Thank you for your interest in the ISI daily bible verse service! You are now subscribed to the MMS bible verse image sent at 7am AZ time. Text "STOP-SERVICES" any time to cancel your subscription.'
    elif current_status == 'HOPE-SMS':
        msg = 'Thank you for your interest in the ISI daily bible verse service! You are now subscribed to the Hope In Numbers MMS sent at 6:33am AZ time. Text "STOP-SERVICES" any time to cancel your subscription.'
    elif current_status == 'STOP-SERVICES':
        msg = """Thank you for your interest in the ISI daily bible verse service! You are now unsubscribed to all services. 
                To resume your subscription, text one of:
                "DAILY-SMS" : daily SMS subscription at 7am.,
                "HOPE-SMS" : daily Hope In Numbers SMS subscription at 6:33am
                """
    else:
        msg = """Thank you for your interest in the ISI daily bible verse service. 
                 The keyword you sent is not among the available options. Please choose from the following: 
                 "DAILY-SMS" : daily SMS subscription at 7am.,
                 "DAILY-IMAGE" : daily MMS verse image subscription at 7am.,
                 "HOPE-SMS" : daily Hope In Numbers SMS subscription at 6:33am,
                 "STOP-SERVICES" : unsubscribe from all services.
            """

    if current_status in ('DAILY-SMS', 'STOP-SERVICES', 'HOPE-SMS'):
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(USERS_TABLE)

        try:
            response = table.update_item(
                        Key={'phone_number': phone_number},
                        UpdateExpression="set current_status = :s",
                        ExpressionAttributeValues={
                            ':s': current_status},
                        ReturnValues="UPDATED_NEW")
        except ClientError as err:
            logger.error(
                        "Couldn't update item %s in table %s. Here's why: %s: %s",
                        phone_number, table.name,
                        err.response['Error']['Code'], err.response['Error']['Message'])
            raise
        else:
            print(response['Attributes'])
        
    #create response
    resp = MessagingResponse()
    resp.message(msg)

    return str(resp), 200, {'Content-Type': 'application/xml'}


@app.errorhandler(404)
def resource_not_found(e):
    return make_response(jsonify(error='Not found!'), 404)
