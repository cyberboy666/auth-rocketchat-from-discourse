# discourse-cas-bridge
small flask auth bridge - using discourse as an sso provider for rocket.chat

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
