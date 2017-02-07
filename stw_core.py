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


def assert_ok(response):
    if response.status_code != 200:
        raise Exception("Invalid response for " + response.url)


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
    assert_ok(loginPage)

    [username, password] = get_auth_config()

    loginForm = loginPage.soup.select("form#aspnetForm")[0]
    loginForm.select("#username")[0]['value'] = username
    loginForm.select("#password")[0]['value'] = password

    print("Logging in (username: {0})...".format(username))
    redirectPage = browser.submit(loginForm, loginPage.url)
    assert_ok(redirectPage)

    redirectForm = redirectPage.soup.select("form")[0]

    mainPageUrl = redirectForm["action"]
    mainPage = browser.submit(redirectForm, mainPageUrl)
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
    assert_ok(sslPage)
    is_ssl_module_loaded = True


def get_site_info(domain):
    global sslPageUrl, site_infos

    if domain not in site_infos:
        get_ssl_module()
        print("Looking up domain-info ({0})...".format(domain))
        timestamp = str(int(datetime.datetime.now().timestamp()))
        searchUrl = sslPageUrl + "/SearchAutocomplete?q=" + domain + "&limit=10&timestamp=" + timestamp
        sslIdResponse = browser.get(searchUrl)
        assert_ok(sslIdResponse)

        [site, guid] = sslIdResponse.text.split("|")
        print("- Found site-id: {0}".format(guid))
        site_infos[domain] = [site, guid]

    return site_infos[domain]


def get_ssl_info(domain):
    [site, guid] = get_site_info(domain)

    getListUrl = sslPageUrl + "/Search?sEcho=2&iColumns=7&sColumns=&iDisplayLength=10&iDisplayStart=0&sSearch=&bEscapeRegex=true&sSearch_0=&bEscapeRegex_0=true&sSearch_1=&bEscapeRegex_1=true&sSearch_2=&bEscapeRegex_2=true&sSearch_3=&bEscapeRegex_3=true&sSearch_4=&bEscapeRegex_4=true&sSearch_5=&bEscapeRegex_5=true&sSearch_6=&bEscapeRegex_6=true&iSortingCols=1&iSortCol_0=0&iSortDir_0=asc&adSearchQuery=" + guid + "&dName=" + site

    print("Looking up SSL-info...")
    getListResponse = browser.get(getListUrl)
    assert_ok(getListResponse)

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
    assert_ok(getCertificateResponse)

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


def update_certificate(domain, certfile, keyfile):
    [needs_update, expiration] = certificate_needs_update(domain)
    if not needs_update:
        print("Current certificate not near expiration: {0}".format(expiration))
        print("Not updating.")
        return

    print("Updating certificate...")

    logicalId = get_ssl_info(domain)
    updateForm = sslPage.soup.select("form#updateForm")[0]
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
    assert_ok(updateResult)

    print("Verifying...")
    updatedCertInfo = get_certificate_info(logicalId)
    updatedCert = updatedCertInfo["Certificate"]
    updatedKey = updatedCertInfo["Key"]

    assert_equalish(certfile, updatedCert)
    assert_equalish(keyfile, updatedKey)
    print("Certificate updated!")

