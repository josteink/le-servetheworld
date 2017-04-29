#!/usr/bin/python3

import mechanicalsoup
import datetime
import json


# utility functions

def read_file(filename):
    with open(filename) as f:
        result = f.read()
        return result


def parse_date(str):
    format = "%b %d %H:%M:%S %Y %Z"
    result = datetime.datetime.strptime(str, format)
    return result


def normalize(str):
    return str.replace("\r\n", "\n").strip()


def assert_equalish(filename, value):
    original = read_file(filename)

    n_original = normalize(original)
    n_value = normalize(value)

    if (n_original != n_value):
        raise Exception("Certificate component {0} was not updated on server!".format(filename))


# global objects
browser = mechanicalsoup.Browser()
loginUrl = "https://hcp.stwcp.net/"

is_logged_in = False
mainPageUrl = ""
mainPage = None

sslPage = None
sslPageUrl = None
is_ssl_module_loaded = False

site_infos = {}


def get_auth_config():
    config = read_file("./stw.json")
    config_json = json.loads(config)
    return [config_json["username"], config_json["password"]]


def login():
    global is_logged_in, mainPage, mainPageUrl
    if is_logged_in:
        return

    print("Loading login page ({0})...".format(loginUrl))
    loginPage = browser.get(loginUrl)
    loginPage.raise_for_status()

    [username, password] = get_auth_config()

    loginForm = loginPage.soup.select("form#aspnetForm")[0]
    loginForm.select("#username")[0]['value'] = username
    loginForm.select("#password")[0]['value'] = password

    print("Logging in (username: {0})...".format(username))
    redirectPage = browser.submit(loginForm, loginPage.url)
    redirectPage.raise_for_status()

    redirectForm = redirectPage.soup.select("form")[0]

    # avoid double root-slash in URLs made later
    mainPageUrl = redirectForm["action"][:-1]
    mainPage = browser.submit(redirectForm, mainPageUrl)
    mainPage.raise_for_status()
    is_logged_in = True


def get_ssl_module():
    global is_ssl_module_loaded, sslPage, sslPageUrl
    if is_ssl_module_loaded:
        return

    login()
    sslLink = mainPage.soup.find("a", text="SSL certificates")
    sslPageUrl = mainPageUrl + sslLink["href"]

    print("Loading SSL-module ({0})...".format(sslPageUrl))
    sslPage = browser.get(sslPageUrl)
    sslPage.raise_for_status()
    is_ssl_module_loaded = True


def get_site_info(domain):
    global sslPageUrl, site_infos

    if domain not in site_infos:
        get_ssl_module()
        print("Looking up domain-info ({0})...".format(domain))
        timestamp = str(int(datetime.datetime.now().timestamp()))
        searchUrl = sslPageUrl + "/SearchAutocomplete?q=" + domain + "&limit=10&timestamp=" + timestamp
        sslIdResponse = browser.get(searchUrl)
        sslIdResponse.raise_for_status()

        [site, guid] = sslIdResponse.text.split("|")
        print("- Found site-id: {0}".format(guid))
        site_infos[domain] = [site, guid]

    return site_infos[domain]


def get_request_verification_token():
    get_ssl_module()
    input = sslPage.soup.select("input[name=='__RequestVerificationToken']")[0]
    token = input["value"]
    return token


def get_ssl_info(domain):
    [site, guid] = get_site_info(domain)

    getListUrl = sslPageUrl + "/Search"
    payload = {}

    payload["sEcho"] = "5"
    payload["iColumns"] = "8"
    payload["sColumns"] = ",,,,,,,"
    payload["iDisplayLength"] = "10"
    payload["iDisplayStart"] = "0"

    # nonsortable
    for n in [0, 7]:
        ns = str(n)
        payload["mDataProp_" + ns] = ns
        payload["sSearch_" + ns] = ""
        payload["bRegex_" + ns] = "false"
        payload["bSearchable_" + ns] = "true"
        payload["bSortable_" + ns] = "false"

    # sortable
    for n in range(1, 6):
        ns = str(n)
        payload["mDataProp_" + ns] = ns
        payload["sSearch_" + ns] = ""
        payload["bRegex_" + ns] = "false"
        payload["bSearchable_" + ns] = "true"
        payload["bSortable_" + ns] = "true"

    payload["sSearch"] = domain
    payload["bRegex"] = "false"
    payload["iSortingCols"] = "1"
    payload["iSortCol_0"] = "6"
    payload["iSortDir_0"] = "asc"
    payload["adSearchQuery"] = guid
    payload["dName"] = site
    token = get_request_verification_token()
    payload["__RequestVerificationToken"] = token

    print("Looking up SSL-info...")
    getListResponse = browser.post(getListUrl, data=payload)
    getListResponse.raise_for_status()

    getListJson = json.loads(getListResponse.text)
    aaData = getListJson["aaData"]
    if len(aaData) == 0:
        print("- No certificates found!")
        return None

    siteInfo = getListJson["aaData"][0][5]
    siteInfoJson = json.loads(siteInfo)

    logicalId = siteInfoJson["logicalID"]
    print("- Found certificate-ID: {0}".format(logicalId))
    return logicalId


def get_certificate_info(domain):
    logicalId = get_ssl_info(domain)
    if logicalId is None:
        return None

    print("Looking up certificate...")
    getCertificateUrl = sslPageUrl + "/GetCertificate?adSearchQuery=" + logicalId

    getCertificateResponse = browser.get(getCertificateUrl)
    getCertificateResponse.raise_for_status()

    certJson = json.loads(getCertificateResponse.text)
    return certJson


def certificate_needs_update(domain):
    currentCertInfo = get_certificate_info(domain)
    if currentCertInfo is None:
        return [True, None]

    currentValid = currentCertInfo["To"]
    currentValidDate = parse_date(currentValid)

    expirationThreshold = datetime.datetime.now() + datetime.timedelta(days=7)
    return [currentValidDate <= expirationThreshold, currentValid]


def add_new_certificate(domain, certfile, keyfile):
    [needs_update, expiration] = certificate_needs_update(domain)
    if not needs_update:
        print("Current certificate not near expiration: {0}".format(expiration))
        print("Not updating.")
        return

    print("Adding new certificate...")
    addForm = sslPage.soup.select("form#iHaveCertAddForm")[0]

    addForm.select("#HaveCertificate_CommonName")[0]["value"] = domain
    addForm.select("#HaveCertificate_CertificateFile")[0]["value"] = certfile
    addForm.select("#HaveCertificate_KeyFile")[0]["value"] = keyfile
    addUrl = mainPageUrl + addForm["action"]

    addResult = browser.submit(addForm, addUrl)
    addResult.raise_for_status()

    addResultContents = addResult.soup.select("textarea")[0]
    addResultJson = json.loads(addResultContents.getText())
    if addResultJson["success"] == "FALSE":
        raise Exception("Error uploading certificate: " + addResultJson["info"][0]["message"])

    print("Verifying...")
    logicalId = get_ssl_info(domain)
    if logicalId is None:
        raise Exception("No certificate registered after upload!")

    addedCertInfo = get_certificate_info(logicalId)
    addedCert = addedCertInfo["Certificate"]
    addedKey = addedCertInfo["Key"]

    assert_equalish(certfile, addedCert)
    assert_equalish(keyfile, addedKey)
    print("Certificate updated!")


def update_certificate(domain, certfile, keyfile):
    [needs_update, expiration] = certificate_needs_update(domain)
    if not needs_update:
        print("Current certificate not near expiration: {0}".format(expiration))
        print("Not updating.")
        return

    updateForm = sslPage.soup.select("form#updateForm")[0]

    logicalId = get_ssl_info(domain)
    print("Updating certificate...")
    logicalIdTag = sslPage.soup.new_tag("input")
    logicalIdTag["type"] = "hidden"
    logicalIdTag["name"] = "LogicalID"
    logicalIdTag["id"] = "LogicalID"
    logicalIdTag["value"] = logicalId
    updateForm.append(logicalIdTag)

    updateForm.select("#add_cert_upload")[0]["value"] = certfile
    updateForm.select("#add_key_upload")[0]["value"] = keyfile
    updateUrl = mainPageUrl + updateForm["action"]

    updateResult = browser.submit(updateForm, updateUrl)
    updateResult.raise_for_status()

    print("Verifying...")
    updatedCertInfo = get_certificate_info(logicalId)
    updatedCert = updatedCertInfo["Certificate"]
    updatedKey = updatedCertInfo["Key"]

    assert_equalish(certfile, updatedCert)
    assert_equalish(keyfile, updatedKey)
    print("Certificate updated!")


def upload_certificate(domain, certfile, keyfile):
    [needs_update, expiration] = certificate_needs_update(domain)
    if not needs_update:
        print("Current certificate not near expiration: {0}".format(expiration))
        print("Not updating.")
        return

    if expiration is None:
        add_new_certificate(domain, certfile, keyfile)
    else:
        update_certificate(domain, certfile, keyfile)

