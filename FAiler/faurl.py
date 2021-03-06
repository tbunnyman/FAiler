#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import os
import urllib2
import FAiler
from datetime import datetime
from bs4 import BeautifulSoup
from mechanize import Browser
from FAiler.exceptions import FAError, FAAuth


class FAUrl():
    """
    This represents all the urls and information on the FurAffinity website.

    This object does all of it's work during init so creating them will be
     expensive because of the calls to FA. Afterwards there should be no
     further calls.

    According to FA there are three types of Submissions; Visual, Textual, &
     Audio. These are constants for the object

    """
    VISUAL_TYPE = 1
    TEXTUAL_TYPE = 2
    AUDIO_TYPE = 3

    def __init__(self, submissionUrl, username=None, password=None, br=None):
        """
        The object needs a furaffinity submission link.

        If you opt to NOT submit a username and password to FA then checks to
         adult submissions will fail with exception.

        Optionally you can pass your own Mechanize browser that already has all
         the authentication and cookies you need. this is highly advanced
         usage but is best if used in any bulk instance. You should verify
         your browser instance is properly authenticated or errors will occur.

        :param submissionUrl: Full url to a submission page
        :param username: Your FA Username used to check mature+ submissions
        :param password: Your FA Password used to check mature+ submissions
        :param br: An already authorized mechanize browser instance

        :raise: FAError if the url is not recognizable or FA fails
        :raise: FAAuth if username & password is bad
        """
        self._username = username
        self._password = password
        self._br = br

        submissionRe = re.compile(
            r"https?://www\.furaffinity\.net/(view|full)/(?P<number>\d+)/")
        submissionMatch = re.match(submissionRe, submissionUrl)
        if submissionMatch is None:
            raise FAError("Unsupported/Unparseable URL")

        self.link = submissionUrl
        self.number = submissionMatch.group('number')
        br = self.get_browser()
        try:
            soup = BeautifulSoup(br.open(self.link))
        except urllib2.HTTPError:
            raise FAError("FA's down, F5 time.")
        if soup.find('div', id="submission") is None:
            raise FAAuth("Submission blocked. Please login")

        # Parse out FACDN submission link
        rawRe = re.compile(r" Download")
        try:
            link = soup.find('a', text=rawRe).get('href')
        except AttributeError:
            raise FAError("Pulling facdn failed. Parsing Failure")
        self.artLink = 'http:' + link

        # Parse out info from FACDN
        # Sorry for the regexp
        facdnRe = re.compile(r"""https?://d\.facdn\.net/art/      # Leader
                                (?P<user>[\w\[\]~.-]+?)           # User
                                (?P<category>/stories/|/music/|/) # category
                                (?P<date>\d+)\.                   # FAile
                                (?P<useragain>[\w\[\]~.-]+?)_
                                (?P<name>\S+)\.
                                (?P<ext>\w{2,4})""", re.VERBOSE)

        match = re.match(facdnRe, self.artLink)
        try:
            self.artist, self.category, self.date = match.group(1, 2, 3)
            self.submissionName = match.expand(r"\3.\4_\5.\6")
        except AttributeError:
            raise FAError('Could not parse facdn url ' + self.artLink)

        # Parse out SFW rating
        self.rating = soup.find(
            'img', alt=re.compile(r'(\w) rating')).get('alt')
        self.sfw = False
        if self.rating == 'General rating':
            self.sfw = True

        # Parse out title
        self.title = soup.find('img', id="submissionImg").get('alt')

        # Parse out keywords
        keysRe = re.compile("/search/@keywords.*")
        self.keywords = [x.string for x in soup.find_all('a', href=keysRe)]

        # TODO Parse out submission information

    def __repr__(self):
        call = [self.link]
        if self._username is not None:
            call.append("username={}".format(self._username))
        if self._password is not None:
            call.append("password={}".format(self._password))
        return "FAUrl({})".format(", ".join(call))

    def __str__(self):
        return str(self.link)

    def get_title(self):
        return self.title

    def get_link(self):
        return self.link

    def get_number(self):
        return self.number

    def get_art_link(self):
        return self.artLink

    def get_date(self):
        """
        :return: datetime object
        """
        return datetime.fromtimestamp(self.date)

    def get_keywords(self):
        """
        :return: Array of keywords
        """
        return self.keywords

    def get_category(self):
        """
        VISUAL_TYPE
        TEXTUAL_TYPE
        AUDIO_TYPE
        :return: a *_TYPE constant of the FAUrl
        """
        if self.category == '/':
            return FAUrl.VISUAL_TYPE
        elif self.category == '/stories/':
            return FAUrl.TEXTUAL_TYPE
        elif self.category == '/music/':
            return FAUrl.AUDIO_TYPE

    def get_artist(self):
        return self.artist

    def get_rating(self):
        return self.rating

    def is_safe_for_work(self):
        return self.sfw

    def get_faile(self):
        return FAiler.FAile(self.submissionName)

    def download_submission(self, directory, filename=None):
        """
        Downloads the submitted FA art to the supplies directory optionally
         with an alternite filename

        :param directory: Directory to write file to.
        :param filename: Name of file to save to. If None uses FA filename

        :raises: IOError if it cannot write to directory
        :raises: FAError if we cannot connect to FA
        """
        if filename is None:
            filename = self.submissionName
        filepath = os.path.join(directory, filename)
        try:
            request = urllib2.urlopen(self.artLink)
        except urllib2.HTTPError:
            raise FAError("FA's down, F5 time.")
        with open(filepath, 'w') as f:
            f.write(request.read())

    def get_browser(self):
        """
        Each FAUrl object stores it's own browser instance. On the first call
         it is created and if the username and password is set it will
         authenticate you.

        :return: mechanize.Browser instance.
        :raise: FAiler.FAError if FA is down. Time to F5!
        :raise: FAiler.FAAuth Your username and password failed
        """
        if self._br is None:
            br = Browser()
            br.set_handle_robots(False)
            br.set_handle_redirect(True)
            br.set_handle_referer(True)
            br.set_handle_equiv(True)
            br.addheaders = [('User-agent', 'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.0.1) Gecko/2008071615 Fedora/3.0.1-1.fc9 Firefox/3.0.1')]
            if self._username is not None and self._password is not None:
                loginPage = 'https://www.furaffinity.net/login'
                try:
                    br.open(loginPage)
                except urllib2.HTTPError:
                    raise FAError("FA's down, F5 time.")
                br.form = br.global_form()
                br.form['name'] = self._username
                br.form['pass'] = self._password
                br.form.method = 'POST'
                br.submit()
                if br.geturl() == loginPage + '/?msg=1':
                    raise FAAuth('Username & Password Incorrect')
            self._br = br
        return self._br
