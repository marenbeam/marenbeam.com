% Hosting a static site with Docker, Traefik v2, SSL, and cron
# hosting a static site with docker, traefik v2, ssl, and cron

Just to be clear, this is how I host [this website](https://marenbeam.net).

I hope this post might be helpful for someone using Traefik for the first time, someone moving from Traefik v1 to v2, or someone who's getting familiar with docker compose.

## My use case and constraints

* I want to host many different things on one box. Currently, the most [boring](https://mcfunley.com/choose-boring-technology) way to do that is with docker.
* My previous setup, though technically simple, *felt* overwhelming because I was holding [state](https://en.wikipedia.org/wiki/State_(computer_science)) in my head rather than in text files. Docker would force me to put more system state in text files.

## Parts:

* Debian installed on the server (hereafter referred to as "the host")
* Docker installed on the host
* [Traefik](https://docs.traefik.io/) as an ingress controller for all other docker services
  * Traefik will also handle SSL for us
* [Swarm mode](https://docs.docker.com/engine/swarm/) enabled on the host
* Automatic deploy/update with GitHub and [cron](https://en.wikipedia.org/wiki/Cron)

**Why swarm mode and traefik?** I’ll touch on that in a future post, where I’ll explore how and why you might host a single-node docker cluster in swarm mode.

## Prep:

* Install Debian on the host, and set up SSH
* Install [docker](https://docs.docker.com/install/linux/docker-ce/debian/) and [docker compose](https://docs.docker.com/compose/install/#install-compose-on-linux-systems) on the host
* Enable [`unattended-upgrades`](https://wiki.debian.org/UnattendedUpgrades) on the host
* Set some sane `ufw` rules on the host
* Go to your DNS provider, and create an [A record](https://en.wikipedia.org/wiki/List_of_DNS_record_types) for `mywebsite.com` that points to the IP address of your host

**SSH into the host**, and decide where you want all your docker service configurations to live. I put mine in `~/docker`. They could all go in one `docker-compose.yaml` file, but I put mine in different directories because I have unrelated services running on the same host. If you adhere to the same framework, then you'll want a parent folder for everything, a folder for the ingress controller configuration, a folder for the actual website configuration, and a folder for the source code of the website itself.

```bash
$ mkdir -p ~/docker/traefik
$ mkdir -p ~/docker/mywebsite.com/site
```

And for our last piece of host-setup, we need to enable swarm mode and create a docker network for our services to use.

```bash
$ docker swarm init
$ docker network create --driver overlay proxy
```

We're creating an `overlay` network because this is a swarm node and we'll be deploying swarm services to it. All services will connect to this network so that they can talk to traefik, and traefik will be the only thing that can talk to the internet. You can find more information about docker overlay networks [here](https://docs.docker.com/network/overlay/).

One way to deploy swarm services is to write a `docker-compose.yaml` configuration for each service, and then deploy them with `docker stack deploy`. This is well-supported in the docker documentation, so it's what we're going to do.

```bash
$ vim ~/docker/traefik/docker-compose.yaml
```

Now we can really start doing stuff!

## Configure traefik

First we're going to set up traefik. Paste this configuration into the file you just opened, and edit as necessary for your use case. At the very least, you'll need to change the email address. I've included comments explaining most lines.

```yaml
version: "3"

services:
  traefik:
    # specify the docker image we're deploying as a service
    image: "traefik:latest"
    # this specifies the name of the network the service will connect to
    networks:
      - "proxy"
    # these commands override service configuration defaults
    command:
      # set the service port for incoming http connections
      - "--entrypoints.web.address=:80"
      # set the service port for incoming https connections
      - "--entrypoints.websecure.address=:443"
      # enable the traefik api. this would be used by the traefik dashboard if we set that up
      - "--api=true"
      # tell traefik that it's connecting to a swarm, rather than regular docker
      - "--providers.docker.swarmMode=true"
      # traefik automatically finds services deployed in the swarm ("service discovery").
      # this setting restricts the scope of service discovery to services that set traefik.enable=true
      - "--providers.docker.exposedbydefault=false"

      ### these three lines configure the thing inside of traefik that's going to get/renew/manage SSL certificates for us.
      ### It's called a "certificate resolver"
      # 'leresolver' ("Let's Encrypt resolver") is just the name we're giving to the certificate resolver.
      # The name you choose can be different.
      # set the email address to give Let's Encrypt. we should give them a real email address whose inbox gets checked by a human
      - "--certificatesresolvers.leresolver.acme.email=myemail@mailbox.org"
      # set the location inside the container to store all certificates
      - "--certificatesresolvers.leresolver.acme.storage=/acme.json"
      # tell the certificate resolver the method we want to use to get an SSL certificate.
      # you can read about challenge types here:  https://letsencrypt.org/docs/challenge-types/
      - "--certificatesresolvers.leresolver.acme.tlschallenge=true"

    # because traefik is the ingress controller and thus must talk directly to the internet,
    # we want to bind ports on the traefik container to ports on the debian host. this does that
    ports:
      # container-port:host-port
      - "80:80"
      - "443:443"
    # make things on the host accessible to the container by mounting them in the container
    # /host/path:/container/path
    volumes:
      # mount the docker unix socket inside the traefik container.
      # this is essential for traefik to know about the services it's sending traffic to.
      # we mount it read-only for security. if traefik were compromised, and the docker socket were mounted read/write,
      # the attacker could send instructions to the docker daemon.
      # you can learn about unix sockets here:  https://en.wikipedia.org/wiki/Unix_domain_socket
      - "/var/run/docker.sock:/var/run/docker.sock:ro"
      # mount this file inside the traefik container. this is where SSL certificates are stored.
      # if we don't do this, when traefik reboots (which is guaranteed), we'll lose all our SSL certificates
      - "./acme.json:/acme.json"
    # the deploy block is here because this is a swarm service.
    # other than setting labels, we're using all the swarm mode defaults for this service
    # more information is here: https://docs.docker.com/compose/compose-file/#deploy
    deploy:
      labels:
        # redirect all incoming http requests to https.
        # this will apply to all services sitting behind traefik. for us, that's all services
        - "traefik.http.routers.http-catchall.rule=hostregexp(`{host:.+}`)"
        - "traefik.http.routers.http-catchall.entrypoints=web"
        - "traefik.http.routers.http-catchall.middlewares=redirect-to-https"

        # define a traefik 'middleware' to perform the actual redirect action.
        # more information about traefik middlewares:  https://docs.traefik.io/middlewares/overview/
        # more information about the RedirectScheme middleware:  https://docs.traefik.io/middlewares/redirectscheme/
        - "traefik.http.middlewares.redirect-to-https.redirectscheme.scheme=https"

# this is necessary because we're connecting to a pre-existing network that we made ourselves. in this case, the 'proxy' network
networks:
  # the name of the network
  proxy:
    # this tells docker, "Don't make this network yourself, because I've already made it." It's 'external' to docker-compose
    external: true
```

And that's the main traefik configuration! This may seem like a lot, but we'll never have to touch this configuration again -- even if we deploy 50 unrelated services behind this traefik instance.

Before starting traefik, let's create and set permissions for the `acme.json` file where our certificates will be stored. This file will be full of mission-critical secrets, so it's important to do this right.

```bash
$ touch ~/docker/traefik/acme.json
$ chmod 600 ~/docker/traefik/acme.json
```

And that's truly the end of the traefik configuration :)

One thing that traefik has is [a fancy dashboard](https://docs.traefik.io/v2.0/operations/dashboard/). For clarity of configuration, we've not set that up. Since we've not set that up, and we haven't deployed our website yet, we don't currently have a good way to test our setup. At the moment, the best you can do is deploy traefik and then check to see if it's running. **Reminder**:  we're deploying with `docker stack deploy` because this is a swarm service.

```bash
$ docker stack deploy --compose-file ~/docker/traefik/docker-compose.yaml traefik
$ docker container ls
```

If you see one traefik container running, that's great! You could unplug your server from the wall right now ([not recommended](https://unix.stackexchange.com/questions/12699/do-journaling-filesystems-guarantee-against-corruption-after-a-power-failure)), plug it back in, and the traefik service would automatically come back up as soon as docker was able to make it happen.

Now let's configure our actual website.

## Configure the website

First let's attack the docker service configuration. Open a new compose file:

```bash
$ vim ~/docker/mywebsite.com/docker-compose.yaml
```

And paste in the following configuration. Again, edit as necessary for your use case:

```yaml
version: '3'

services:
  nginx:
    # we specify that we want to use the alpine-based nginx image
    image: "nginx:alpine"
    # connect to this network in order to connect to traefik
    networks:
      - "proxy"
    # mount the directory containing the source code for our website inside the container.
    # this is the directory that the default nginx configuration automatically serves content from.
    # by putting our site here, we avoid having to write any nginx configuration ourselves
    volumes:
      - "./site:/usr/share/nginx/html:ro"
    deploy:
      labels:
        # tell traefik that it can automatically "discover" this service
        - "traefik.enable=true"
        # tell traefik that all requests for 'mywebsite.com' should be sent to this service
        - "traefik.http.routers.mywebsite.rule=Host(`mywebsite.com`)"
        # only allow incoming https connections
        - "traefik.http.routers.mywebsite.entrypoints=websecure"
        # tell traefik which certificate resolver to use to issue an SSL certificate for this service
        # the one we've created is called 'leresolver', so this must also use 'leresolver'
        - "traefik.http.routers.mywebsite.tls.certresolver=leresolver"
        # tell traefik which port *on this service* to connect to.
        # this is necessary only because it's a swarm service.
        # more info is here: https://docs.traefik.io/providers/docker/#port-detection_1
        - "traefik.http.services.mywebsite.loadbalancer.server.port=80"

# again, we have to specify that we've already created this network
networks:
  proxy:
    external: true
```

**Now we can do a quick test** to see whether everything's working up to this point.

```bash
$ echo 'hello world' > ~/docker/mywebsite.com/site/index.html
$ docker stack deploy --compose-file ~/docker/mywebsite/docker-compose.yaml mywebsite
```

Wait for 30 seconds, just for good measure :)  Consider making some tea!
Then, visit `mywebsite.com` in a browser, or on your local machine:

```bash
$ curl https://mywebsite.com
```

If you get a response (or a page) containing only `hello world` -- success!

Now we can do the last step:  setting up automatic deployments with GitHub and cron. If you don't already have a static site you'd like to use for this, you can use [this template](https://github.com/marenbeam/mynamedotcom) to start with.

## Set up automatic deployments

Our end-goal workflow for making changes to our site is:

1. Make changes to our website on our local machine
1. Assuming our source code is in a public repo on GitHub, commit our changes and run `git push`
1. At the top of the next hour, our changes are visible on the internet

We're going to use a cron job running on the host to achieve this. **Yes, this is a pretty funny combination of fancy-pants new tech (traefik, swarm mode, etc.), and timeless old-school tech (cron)**. We *could* have a deployment pipeline that builds our site into a container for us when we push to master, and then pulls the image from a private container registry. However, such a solution is overengineered for my particular use case. For the most part, the rest of the stuff running on my server is Other People's Software that I use to collaborate with friends on projects or to [self-host](https://github.com/awesome-selfhosted/awesome-selfhosted) things I use in my day-to-day life. That means I'm using other people's compose files, and pulling other people's public images -- none of which requires setting up my own CI/CD, managing private keys on the host, or managing my own infrastructure outside of the server itself. So I want to avoid overly-complex solutions for hosting an ultra-simple personal website, with the caveat that it needs to be served from docker since that's what the rest of my setup requires.

Moving on, we're going to skip over creating a new repo and just work with [this template](https://github.com/marenbeam/mynamedotcom) (which you should absolutely feel free to use for your own website!)

Assuming you've forked my repo, or are otherwise set up with a git repo you'd like to use, now we just need to set up a cron job on our host that'll pull the repo each hour and copy it into `~/docker/mywebsite.com/site` for nginx to serve.

First, **SSH into the host**, and:

```bash
$ mkdir ~/cronjobs
$ mkdir ~/.mywebsite.com
$ vim ~/cronjobs/update-my-website-dot-com.sh
```

In the file you just opened, paste the following:

```bash
#!/bin/bash
cd ~/.mywebsite.com/mywebsite.com
git pull
# we only want to give nginx the files that we actually want to serve.
# we include the --delete flag so that if we permanently remove a file from our site's source code,
# it's removed from the directory that nginx is serving.
# basically, a true "sync" with rsync requires the --delete flag
rsync -a --delete --exclude '.*' --exclude 'README.md' --exclude 'LICENSE' . ~/docker/mywebsite.com/site/
```

Make the update script executable, and for good measure be sure `rsync` and `git` are installed:

```bash
$ chmod +x ~/cronjobs/update-my-website-dot-com.sh
$ sudo apt update
$ sudo apt install rsync git
```

Now get the repo onto the host, and into the right place -- we only have to do this once.

```bash
$ cd ~/.mywebsite.com
$ git clone https://github.com/marenbeam/mynamedotcom.git
```

Run the update script once manually to sync the repo right now:

```bash
$ ~/cronjobs/update-my-website-dot-com.sh
```

Finally, cron it:

```bash
$ crontab -e
```

And in that file add the line:

```bash
@hourly ~/cronjobs/update-my-website-dot-com.sh
```

**And that's it!** You've now got a single node docker swarm cluster; traefik accepting incoming requests, routing them to the appropriate service, and programmatically handling SSL provisioning and termination; an nginx container serving your static site over https; and a cute little cronjob syncing and deploying all changes merged to `master` at the top of each hour :)

Thanks so much for reading!
