
# le-servetheworld

The web-hosting company [servetheworld.net](https://servetheworld.net)
does currently not support [Letsencrypt](https://letsencrypt.org/).

This repo contains some scripts and recipes for web-sites hosted by
servetheworld.net (hereby referred to as STW), to assist in
Letsencrypt based automatic certificate-management.

## prerequisites

- python 3
- mechanicalsoup python 3 module (install using pip3)

## disclaimer

These scripts and recipes are provided as is with no warranties and no
liabilities accepted for issues cause by using them.

These are scripts which are using your login-credentials, to pretend
they are human and poke around inside your STW control-panel
([http://hcp.stwcp.net/](http://hcp.stwcp.net/)).

Although precautions have been put in place to bail out early when the
scripts encounter unexpected results, obviously worst-case scenarios
can be catastrophic.

If errors happen, feel free to file a bug-report, but don't expect me
to take on any responsibility for your losses.

## basic usage - acquire certificates

1. Setup a website on a server you control, where you can successfully
   navigate given a DNS-name you control (this can be DynDNS or
   anything "basic" like that).

2. Setup and run a Letsencrypt ACME client (like
   [dehydrated](https://github.com/lukas2511/dehydrated/),
   [ACME tiny](https://github.com/diafygi/acme-tiny) or
   [Certbot](https://github.com/certbot/certbot)) for this
   server. Verify that you are successfully able to retrieve
   certificates for this server before moving on.
   
3. Upload a `.htaccess` file to your STW website-folder (where you
   keep your `index.html`, etc).
   
   This file needs to contain the following snippet:
   
   ````
   RedirectMatch 301 /.well-known/acme-challenge/(.*) http://your.acme-client.domain/.well-known/acme-challenge/$1
   ````

4. Run your Letsencrypt ACME-client of choice on your own server, for
   the domain hosted by STW.
   

If all succeeds, you should now have certificates for your STW website
available on the machine where you ran the ACME-client.

## upload automation

Use whatever daemon or scheduler you like to automate the process of
getting certificates.

Once you have that done, you can use the python-script provided in
this repo to automate upload and installation of this certificate:

The script needs to be able to authenticate against your control
panel. For this it needs your login credentials stored in a file
called `stw.json`, in the same folder as the rest of the scripts.

````json
{
    "username": "your@login.here",
    "password": "your.password.here"
}
````

With this in place, you should be able to update your certificates
using the following command:

````
$ ./stw_update_cert your.domain.here your_domains_fullchain.pem your_domains_key.pem
````

The script itself verifies that the uploaded certificate gets
registered on the server, so if you find the updated certificate
doesn't seem to work, try manually uploading it in the control-panel
and wait it out.

If that doesn't work, it's clearly a support-issue for STW and not for
these scripts :)

Cheers.
