"""
.. module:: fb_client
    :synopsis: customized fbchat client for sending/receiving messages

.. moduleauthor:: Tomas Choi <choitomas66@gmail.com>
"""

from fbchat import Client
from fbchat.models import Message
from fbchat.models import ThreadType
from fbchat.models import Mention
from fb_client_exceptions import FBClientError
from getpass import getpass
import logging
from stoppable_thread import StoppableThread
from time import sleep

class fb_client(Client):

    def __init__(self, email=None, password=None, user_agent=None, \
        max_tries=5, session_cookies=None, logging_level=logging.INFO):
        """ Overrides parent constructor to make email and password
            optional. (This helps because we primarily use session
            cookies to log users back in)

            Args:
                | email: Facebook login email
                | password: Facebook login password
                | max_tries: maximum login attempts
                | session_cookies: Cookies from a previous session
                | logging_level: Configures the `logging level` \
                    Defaults to logging.INFO

            Raises:
                FBchatException on failed login
        """

        super(fb_client, self).__init__(email=email, password=password, \
            max_tries=max_tries, session_cookies=session_cookies,
            logging_level=logging_level)


    def _extract_mentions(self, message_text):
        """ Takes message in raw text form and returns
            a list of appropriate Mentions objects

            Args:
                message_text: message in raw text form

            Returns:
                A list of :class:`fbchat.models.Mention` objects
        """

        # Find all occurrences of @ (for offset)
        index = 0
        mention = []
        at_indices = []

        for c in message_text:
            if c is '@':
                at_indices.append(index)
            index += 1

        # used for offset
        at_count = 0

        elements = message_text.split(" ")
        for element in elements:
            # look for @s
            if element.startswith("@"):
                users = self.searchForUsers(element[1:])

                # @ is a valid Mention
                if len(users) is not 0:
                    user = users[0]
                    mention.append( \
                        Mention(user.uid, offset=at_indices[at_count], \
                            length=len(element)))

                at_count += 1

        return (None if len(mention) is 0 else mention)


    def _construct_message_from_text(self, message_text):
        """ Takes message in raw text form and constructs a
            :class:`fbchat.models.Message object`

        Args:
            message_text: message in raw text form

        Returns:
            :class:`fbchat.models.Message` object representing
            raw text message input
        """

        mentions = self._extract_mentions(message_text)

        return Message(text=message_text, mentions=mentions)


    def send_message(self, message_text, user_uid=None, group_uid=None):
        """ Sends a appropriately constructed message given
            raw text message input.
        Args:
            | message_text: message in raw text form
            | user_uid: uid of user
            | group_uid: uid of group

        Raises:
            FBClientError on missing user_uid and group_uid
                or when both are provided

        """

        if user_uid is None and group_uid is None:
            raise FBClientError("Must provide a user_uid or group_uid")
        if user_uid is not None and group_uid is not None:
            raise FBClientError("Must only provide one of either a " + \
                "user_uid or group_uid")

        if user_uid is not None:
            self.send(self._construct_message_from_text(message_text), \
                    thread_id=user_uid, thread_type=ThreadType.USER)
        elif group_uid is not None:
            self.send(self._construct_message_from_text(message_text), \
                    thread_id=group_uid, thread_type=ThreadType.GROUP)


    def _listen_daemon(self):
        """ listener that runs until the thread it is part
            of is terminated. Not a true daemon, but purpose
            is to make the listening process run on a separate
            thread.
        """

        self.startListening()
        self.onListening()
        while self.thread.is_running() and self.doOneListen():
            pass

        self.stopListening()
        self.thread.stopped()


    def start_listen(self):
        """ Creates and starts a listener thread.

            Raises:
                FBClientError if client is already listening
        """

        try:
            self.thread
            raise FBClientError("Called start_listen when " + \
                    "client is already listening")
        except AttributeError:
            logging.info('Client is listening...')
            self.thread = StoppableThread(name="listen", target=self._listen_daemon, args=())
            self.thread.start()


    def stop_listen(self):
        """ "Terminates" the listener thread.

            Raises:
                FBClientError if client has not been listening
        """

        try:
            self.thread
        except AttributeError:
            raise FBClientError("Called stop_listen when " + \
                    "client was not listening")

        if self.thread.is_running():
            print "Stopping client listen..."
            self.thread.stop()
            self.thread.join()
            logging.info('Client stopped listening')
            del self.thread

