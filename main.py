import string, random
from flask import Flask, request, redirect, Response
from base64 import b64encode, b64decode
from urllib.parse import quote_plus, parse_qs, urlparse
from datetime import datetime, timedelta
from lxml import etree
import hmac
import hashlib 

app = Flask(__name__)

sso_secret = '' ## this is set in the discourse login menu
bridge_base_url = ''
discourse_base_url = ''

memory_store = {}


@app.route('/auth/forward')
def forward_request():
    '''
        From discourse sso wiki:
        > Generate a random nonce - Save it temporarily so that you can verify it with returned nonce value
        > Create a new payload with nonce and return url (where the Discourse will redirect user after verification). Payload should look like: nonce=NONCE&return_sso_url=RETURN_URL
        > Base64 encode the above raw payload. Let’s call this payload as BASE64_PAYLOAD
        > URL encode the above BASE64_PAYLOAD. Let’s call this payload as URL_ENCODED_PAYLOAD
        > Generate a HMAC-SHA256 signature from BASE64_PAYLOAD using your sso provider secret as the key, then create a lower case hex string from this. Let’s call this signature as HEX_SIGNATURE
        > Redirect the user to DISCOURSE_ROOT_URL/session/sso_provider?sso=URL_ENCODED_PAYLOAD&sig=HEX_SIGNATURE

        note here we use the rocketchat token as nonce
    '''
    global memory_store
    service_url = request.args.get('service')
    return_url = f'{bridge_base_url}/return'
    token = urlparse(service_url).path.split('/')[-1]
    add_token_to_memory_store(token, memory_store)
    memory_store[token]['service_url'] = service_url

    payload =f'nonce={token}&return_sso_url={return_url}'
    payload_bytes = payload.encode('ascii')
    base64_bytes = b64encode(payload_bytes)
    base64_payload = base64_bytes.decode('ascii')
    url_encoded_payload = quote_plus(base64_payload)
    hex_signature = create_sha256_signature(sso_secret, base64_payload)

    return redirect(f'{discourse_base_url}/session/sso_provider?sso={url_encoded_payload}&sig={hex_signature}', code=302)


@app.route('/auth/return')
def return_request():
    '''
        From discourse sso wiki:
        > Compute the HMAC-SHA256 of sso using sso provider secret as your key.
        > Convert sig from it’s hex string representation back into bytes.
        > Make sure the above two values are equal.
        > Base64 decode sso, you’ll get the passed embedded query string. This will have a key called nonce whose value should match the nonce passed originally. Make sure that this is the case.
        > You’ll find this query string will also contain a bunch of user information, use as you see fit.

        after passing these checks we generate a ticket for this request and put all the info in the memory-store
    '''
    global memory_store
    sso = request.args.get('sso')
    sig = request.args.get('sig')

    sso_signature = create_sha256_signature(sso_secret, sso)
    sso_signature_bytes = sso_signature.encode('utf-8')
    sig_bytes = sig.encode('utf-8')
    if(sso_signature_bytes != sig_bytes):
        print('signature doesnt match')
        return Response('request failed', 401)
    
    embedded_query_bytes = b64decode(sso)
    embedded_query = embedded_query_bytes.decode('ascii')
    query_dict = parse_qs(embedded_query)

    token = query_dict.get('nonce')[0]
    if not token in memory_store:
        print('token not in store')
        return Response('request failed', 401) 
    
    memory_store[token].update(query_dict)
    ticket = ''.join([random.choice(string.ascii_lowercase) for _ in range(10)])
    memory_store[token]['ticket'] = ticket

    service_url = memory_store[token]['service_url']
    return redirect(f'{service_url}?ticket={ticket}', code=302)


@app.route('/auth/proxyValidate')
def validate_request():
    '''
        check that the ticket send matches the ticket returned. then generate xml for user info
    '''
    global memory_store
    returned_ticket = request.args.get('ticket')
    service_url = request.args.get('service')
    token = urlparse(service_url).path.split('/')[-1]
    if not token in memory_store:
        print('token not in store')
        return Response('request failed', 401) 

    if memory_store[token]['ticket'] != returned_ticket:
        print('ticket doesnt match')
        return Response('request failed', 401) 

    # create XML 
    xcas_namespace = "http://www.yale.edu/tp/cas"
    xcas = "{%s}" % xcas_namespace
    nsmap = {'cas' : xcas_namespace}
    root = etree.Element(xcas + "serviceResponse", nsmap=nsmap)
    success = etree.SubElement(root, xcas + "authenticationSuccess")
    user = etree.SubElement(success, xcas + "user")
    user.text = memory_store[token]['username'][0]
    user = etree.SubElement(success, xcas + "email")
    user.text = memory_store[token]['email'][0]

    xml = etree.tostring(root, pretty_print=True)

    del memory_store[token]
    
    return Response(xml, mimetype='text/xml')


def create_sha256_signature(key, message):
    byte_key = key.encode('utf-8')
    byte_message = message.encode('utf-8')
    return hmac.new(byte_key, byte_message, hashlib.sha256).hexdigest().lower()


def add_token_to_memory_store(new_token, memory_store):
    expires = datetime.now() + timedelta(minutes=10)
    memory_store[new_token] = {'expires_at': expires }
    # remove expired tokens from store
    memory_store = {token:content for token, content in memory_store.items() if content['expires_at'] > datetime.now()}


if __name__ == "__main__":
    app.run(host='0.0.0.0')