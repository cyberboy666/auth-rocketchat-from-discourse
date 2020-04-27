# auth-rocketchat-from-discourse

small flask app that allows using discourse as an sso provider for rocket.chat

__disclaimer:__ this is a hack i made for a small community space. i am not an expert - use at your own risk !

more important details here ...

## background

we host a [discourse](https://www.discourse.org/) [forum](scanlines.xyz) and want to also provide a synchronous chat room using [rocket.chat](rocket.chat) attached to this forum. for this configuration the forum is the main focus and the chatroom an extra service.

I want every user of the forum by default to have access to the chatroom, without needing to create and manage seperate accounts and logins for this service. as this space serves as a refuge from large corporate social media sites i would rather not use an external idenity provider like facebook or google.

## the approach

discourse can act as a [single sign-on provider](https://meta.discourse.org/t/using-discourse-as-a-sso-provider/32974), but this is a [custom protocol](https://meta.discourse.org/t/log-in-to-rocketchat-with-discourse/85559) , more intended for intergration with a website without its own user system. rocket.chat does support sso from a [cas server](https://rocket.chat/docs/administrator-guides/authentication/cas/) - but the flow it expects is different from what discourse provides.

### a good alternative

since both rocket.chat and discourse allow sso from an external [cas server](https://en.wikipedia.org/wiki/Central_Authentication_Service) one way to ensure a single login between them would be to [spin one up](https://nithinkk.wordpress.com/2017/04/01/cas-server-setup-in-10mts/) and send all auth requests to this. this would be espically useful if you wanted to add more cas supporting services to the site.

for our use case it is unlikely we will need additional services. also it makes sense that discourse is the source of auth since this is the main focus of site. we are pushing the virtial machines pretty hard already and running a whole cas server seemed a little overkill (and over complex) for this. also since we have users on the forum already i dont want to think about migrating them to cas.

### a hacky solution

i will run a small [flask](https://flask.palletsprojects.com/en/1.1.x/) service that acts as a bridge between rocket.chat and discourse auth. it performs all the nessicary encoding and hash checks required for discourses sso protocal, and relays this information back to rocket.chat in the cas format it expects.

### request flow

_user redirect and sign-in_

__rocket.chat__ ---> __bridge__ ---> __discourse__

__rocket.chat__ <--- __bridge__ <--- __discourse__

_service-to-service ticket validation_

__rocket.chat__ ---> __bridge__

__rocket.chat__ <--- __bridge__

### endpoints

1. from rocketchat sign-in user is send to the _bridge_:

`GET <bridge>/auth/forward?service=<return_url>`

2. _bridge_ creates and signs the payload for discourse sso then redirects user:

`REDIRECT <discourse>/session/sso_provider?sso={encoded_payload}&sig={hex_sig}`

3. user signs into discourse or creates account if not already logged in. discourse adds idenity information to request and redirects user back to the _bridge_:
  
`GET <bridge>/auth/return?sso={params}&sig={hex_sig}`

4. _bridge_ checks the hashes, creates a ticket and redirects to rocketchat return url:

`REDIRECT <return_url>?ticket={ticket}`

5. _rocketchat_ sends (service-to-service) ticket back to _bridge_ for validation. if ticket matches then idenity information is returned to rocketchat and account is created/logged in:

`GET <bridge>/auth/proxyValidate?ticket={ticket}`

### some cas / related resources that helped:

- https://github.com/RocketChat/Rocket.Chat
- https://apereo.github.io/cas/6.0.x/protocol/CAS-Protocol-V2-Specification.html
- https://kb.iu.edu/d/bfpq
- https://djangocas.dev/docs/latest/CAS-Protocol-Specification.html
- https://codenoble.com/blog/cas-authentication-explained/
- https://docs.traefik.io/routing/routers/
- https://www.digitalocean.com/community/tutorials/how-to-serve-flask-applications-with-gunicorn-and-nginx-on-ubuntu-18-04

# how i set this up

## first configure in the apps

in discourse admin panel go to settings -> login -> scroll to sso options

![image](https://user-images.githubusercontent.com/12017938/80315780-16a97700-87fa-11ea-887f-52a194489e11.png)

you need to check __enable sso provider__ and add your rocketchat url and a secret __sso provider secrets__ here. make sure you really do save this correctly

next in rocketchat admin -> CAS

![image](https://user-images.githubusercontent.com/12017938/80315843-81f34900-87fa-11ea-91b6-fec5f743ceb6.png)

need to enable CAS and set the __SSO Base URL__ and __SSO Login URL__. these should be _<base-url>/auth_ and _<base-url>/auth/forward_

## next the request routing

we are running rocketchat on a digitalocean droplet with [1clickInstall](https://marketplace.digitalocean.com/apps/rocket-chat). this made it a bit difficult to get started because i didnt know how the requests were getting routed to the rocketchat appilication. it seemed neither nginx nor apache were installed on the machine.

running this command was helpful `netstat -tulpn`

![image](https://user-images.githubusercontent.com/12017938/80313835-d3490b80-87ed-11ea-848e-5226f639d156.png)

from here i could see that `traefik` was routing to port 3000 (rocketchat).

`sudo nano /etc//traefik/traefik.toml`

i configured the routing so any requests on the path `/auth` were routed to port `5000` where my flask app would be running

![image](https://user-images.githubusercontent.com/12017938/80314041-1788db80-87ef-11ea-9805-d84f7986dc00.png)

next would be to install _flask_ with _gunicorn_. you need a WSGI application server like Gunicorn because the server that comes with flask is [not meant for production](https://vsupalov.com/flask-web-server-in-production/) (in this case its not really _production_, as only handling a few requests whenever someone logs on to our small forum, but better to be safe - with only a few extra lines)

## finally the application

from here i more or less followed [this guide](https://www.digitalocean.com/community/tutorials/how-to-serve-flask-applications-with-gunicorn-and-nginx-on-ubuntu-18-04) but left our nginx since we are using traefik already. i just pointed it directly to the port rather than with the sock - i dont actually know the difference here, i just left it how i had it set up while testing because it worked.

next step is to clone this repo into home/username/ `git clone https://github.com/langolierz/auth-rocketchat-from-discourse.git` and `cd auth-rocketchat-from-discourse`
  
 edit the _main.py_ file and add your _bridge_base_url_, _discourse_base_url_ and _sso_secret_ from discourse setup.
  
  ![image](https://user-images.githubusercontent.com/12017938/80316391-d1874400-87fd-11ea-941a-8742f70a5254.png)
  
- from within the repo setup virtualenv `python3.6 -m venv auth-rocketchat-from-discourse` and `source auth-rocketchat-from-discourse/bin/activate`
- install dependancies `pip install wheel` and `pip install gunicorn flask lxml`
- leave virtualenv: `deactivate`
- create _systemd_ service unit file: `sudo nano /etc/systemd/system/auth-rocketchat-from-discourse.service` and start it `sudo systemctl start auth-rocketchat-from-discourse` , sudo systemctl enable auth-rocketchat-from-discourse (check status `sudo systemctl status auth-rocketchat-from-discourse`)
 
 ![image](https://user-images.githubusercontent.com/12017938/80342745-f9f65900-8864-11ea-8ad3-d1865f94b684.png)

thats it ! if all went well you should be able to hit the CAS button from the rocketchat signin - which will either take you directly to chat or prompt you to sign in/up at discourse.

### afterthoughts

login/signup with email can be disabled in the rocketchat admin panel. we will force everyone to use a discourse account.

one thing to consider is whether to enable the _Trust CAS username_ inside rocketchat setting. this is risky when left on as any rocketchat account with a username diffent to on discourse can be taken over. however it could be useful to enable just for a short window to allow existing users to pair their accounts. disabling username changing in rocketchat will also reduce this risk. tried to use this to merge existing accounts but it didnt work - i think maybe because we were set to owner of channels and this caused it to fail somehow
