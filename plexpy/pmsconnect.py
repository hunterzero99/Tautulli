# This file is part of PlexPy.
#
#  PlexPy is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  PlexPy is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with PlexPy.  If not, see <http://www.gnu.org/licenses/>.

from plexpy import logger, helpers, common, request

from xml.dom import minidom
from httplib import HTTPSConnection
from httplib import HTTPConnection
from urlparse import parse_qsl
from urllib import urlencode
from pynma import pynma

import base64
import cherrypy
import urllib
import urllib2
import plexpy
import os.path
import subprocess
import json


class PmsConnect(object):
    """
    Retrieve data from Plex Server
    """

    def __init__(self):
        self.host = plexpy.CONFIG.PMS_IP
        self.port = str(plexpy.CONFIG.PMS_PORT)
        self.token = plexpy.CONFIG.PMS_TOKEN

    """
    Return base url of Plex Server.

    Output: string
    """
    def get_base_url(self):
        if self.host != '' and self.port != '':
            base_url = 'http://' + self.host + ':' + self.port
            return base_url
        else:
            return False

    """
    Return current sessions.

    Optional parameters:    output_format { dict, json }

    Output: array
    """
    def get_sessions(self, output_format=''):
        url_command = '/status/sessions'
        http_handler = HTTPConnection(self.host, self.port, timeout=10)

        http_handler.request("GET", url_command + '?X-Plex-Token=' + self.token)
        response = http_handler.getresponse()
        request_status = response.status
        request_content = response.read()

        if output_format == 'dict':
            output = helpers.convert_xml_to_dict(request_content)
        elif output_format == 'json':
            output = helpers.convert_xml_to_json(request_content)
        else:
            output = request_content

        return output

    """
    Return metadata for request item.

    Parameters required:    rating_key { Plex ratingKey }
    Optional parameters:    output_format { dict, json }

    Output: array
    """
    def get_metadata(self, rating_key='', output_format=''):
        url_command = '/library/metadata/' + rating_key
        http_handler = HTTPConnection(self.host, self.port, timeout=10)

        http_handler.request("GET", url_command + '?X-Plex-Token=' + self.token)
        response = http_handler.getresponse()
        request_status = response.status
        request_content = response.read()

        if output_format == 'dict':
            output = helpers.convert_xml_to_dict(request_content)
        elif output_format == 'json':
            output = helpers.convert_xml_to_json(request_content)
        else:
            output = request_content

        return output

    """
    Return processed and validated metadata list for requested item.

    Parameters required:    rating_key { Plex ratingKey }

    Output: array
    """
    def get_metadata_details(self, rating_key=''):
        metadata = self.get_metadata(rating_key)
        metadata_list = []

        try:
            xml_parse = minidom.parseString(metadata)
        except Exception, e:
            logger.warn("Error parsing XML for Plex metadata: %s" % e)
            return None
        except:
            logger.warn("Error parsing XML for Plex metadata.")
            return None

        xml_head = xml_parse.getElementsByTagName('MediaContainer')
        if not xml_head:
            logger.warn("Error parsing XML for Plex metadata.")
            return None

        for a in xml_head:
            if a.getAttribute('size'):
                if a.getAttribute('size') != '1':
                    metadata_list = {'metadata': None}
                    return metadata_list

            if a.getElementsByTagName('Directory'):
                metadata_main = a.getElementsByTagName('Directory')[0]
                metadata_type = self.get_xml_attr(metadata_main, 'type')
                logger.debug(u"Metadata type: %s" % metadata_type)
            elif a.getElementsByTagName('Video'):
                metadata_main = a.getElementsByTagName('Video')[0]
                metadata_type = self.get_xml_attr(metadata_main, 'type')
                logger.debug(u"Metadata type: %s" % metadata_type)
            else:
                logger.debug(u"Metadata failed")

        genres = []
        actors = []
        writers = []
        directors = []

        if metadata_main.getElementsByTagName('Genre'):
            for genre in metadata_main.getElementsByTagName('Genre'):
                genres.append(self.get_xml_attr(genre, 'tag'))
                logger.debug(u"Metadata genre: %s" % self.get_xml_attr(genre, 'tag'))

        if metadata_main.getElementsByTagName('Role'):
            for actor in metadata_main.getElementsByTagName('Role'):
                actors.append(self.get_xml_attr(actor, 'tag'))
                logger.debug(u"Metadata actor: %s" % self.get_xml_attr(actor, 'tag'))

        if metadata_main.getElementsByTagName('Writer'):
            for writer in metadata_main.getElementsByTagName('Writer'):
                writers.append(self.get_xml_attr(writer, 'tag'))
                logger.debug(u"Metadata genre: %s" % self.get_xml_attr(writer, 'tag'))

        if metadata_main.getElementsByTagName('Director'):
            for director in metadata_main.getElementsByTagName('Director'):
                directors.append(self.get_xml_attr(director, 'tag'))
                logger.debug(u"Metadata actor: %s" % self.get_xml_attr(director, 'tag'))

        if metadata_type == 'show':
            metadata = {'type': metadata_type,
                        'ratingKey': self.get_xml_attr(metadata_main, 'ratingKey'),
                        'studio': self.get_xml_attr(metadata_main, 'studio'),
                        'title': self.get_xml_attr(metadata_main, 'title'),
                        'contentRating': self.get_xml_attr(metadata_main, 'contentRating'),
                        'summary': self.get_xml_attr(metadata_main, 'summary'),
                        'rating': self.get_xml_attr(metadata_main, 'rating'),
                        'duration': helpers.convert_milliseconds_to_minutes(self.get_xml_attr(metadata_main, 'duration')),
                        'year': self.get_xml_attr(metadata_main, 'year'),
                        'thumb': self.get_xml_attr(metadata_main, 'thumb'),
                        'art': self.get_xml_attr(metadata_main, 'art'),
                        'originallyAvailableAt': self.get_xml_attr(metadata_main, 'originallyAvailableAt'),
                        'writers': writers,
                        'directors': directors,
                        'genres': genres,
                        'actors': actors
                        }
            metadata_list = {'metadata': metadata}
        elif metadata_type == 'episode':
            metadata = {'type': metadata_type,
                        'ratingKey': self.get_xml_attr(metadata_main, 'ratingKey'),
                        'grandparentTitle': self.get_xml_attr(metadata_main, 'grandparentTitle'),
                        'parentIndex': self.get_xml_attr(metadata_main, 'parentIndex'),
                        'index': self.get_xml_attr(metadata_main, 'index'),
                        'title': self.get_xml_attr(metadata_main, 'title'),
                        'contentRating': self.get_xml_attr(metadata_main, 'contentRating'),
                        'summary': self.get_xml_attr(metadata_main, 'summary'),
                        'duration': helpers.convert_milliseconds_to_minutes(self.get_xml_attr(metadata_main, 'duration')),
                        'year': self.get_xml_attr(metadata_main, 'year'),
                        'thumb': self.get_xml_attr(metadata_main, 'thumb'),
                        'parentThumb': self.get_xml_attr(metadata_main, 'parentThumb'),
                        'art': self.get_xml_attr(metadata_main, 'art'),
                        'originallyAvailableAt': self.get_xml_attr(metadata_main, 'originallyAvailableAt'),
                        'writers': writers,
                        'directors': directors,
                        'genres': genres,
                        'actors': actors
                        }
            metadata_list = {'metadata': metadata}
        elif metadata_type == 'movie':
            metadata = {'type': metadata_type,
                        'ratingKey': self.get_xml_attr(metadata_main, 'ratingKey'),
                        'studio': self.get_xml_attr(metadata_main, 'studio'),
                        'title': self.get_xml_attr(metadata_main, 'title'),
                        'contentRating': self.get_xml_attr(metadata_main, 'contentRating'),
                        'summary': self.get_xml_attr(metadata_main, 'summary'),
                        'rating': self.get_xml_attr(metadata_main, 'rating'),
                        'duration': helpers.convert_milliseconds_to_minutes(self.get_xml_attr(metadata_main, 'duration')),
                        'year': self.get_xml_attr(metadata_main, 'year'),
                        'thumb': self.get_xml_attr(metadata_main, 'thumb'),
                        'art': self.get_xml_attr(metadata_main, 'art'),
                        'originallyAvailableAt': self.get_xml_attr(metadata_main, 'originallyAvailableAt'),
                        'genres': genres,
                        'actors': actors,
                        'writers': writers,
                        'directors': directors
                        }
            metadata_list = {'metadata': metadata}
        elif metadata_type == 'season':
            metadata = {'type': metadata_type,
                        'ratingKey': self.get_xml_attr(metadata_main, 'ratingKey'),
                        'parentTitle': self.get_xml_attr(metadata_main, 'parentTitle'),
                        'index': self.get_xml_attr(metadata_main, 'index'),
                        'title': self.get_xml_attr(metadata_main, 'title'),
                        'thumb': self.get_xml_attr(metadata_main, 'thumb'),
                        'art': self.get_xml_attr(metadata_main, 'art'),
                        }
            metadata_list = {'metadata': metadata}
        else:
            return None

        return metadata_list

    """
    Validate xml keys to make sure they exist and return their attribute value, return blank value is none found
    """
    def get_xml_attr(self, xml_key, attribute, return_bool=False, default_return=''):
        if xml_key.getAttribute(attribute):
            if return_bool:
                return True
            else:
                return xml_key.getAttribute(attribute)
        else:
            if return_bool:
                return False
            else:
                return default_return

    """
    Return processed and validated session list.

    Output: array
    """
    def get_current_activity(self):
        session_data = self.get_sessions()
        session_list = []

        try:
            xml_parse = minidom.parseString(session_data)
        except Exception, e:
            logger.warn("Error parsing XML for Plex session data: %s" % e)
            return None
        except:
            logger.warn("Error parsing XML for Plex session data.")
            return None

        xml_head = xml_parse.getElementsByTagName('MediaContainer')
        if not xml_head:
            logger.warn("Error parsing XML for Plex session data.")
            return None

        for a in xml_head:
            if a.getAttribute('size'):
                if a.getAttribute('size') == '0':
                    logger.debug(u"No active sessions.")
                    session_list = {'stream_count': '0',
                                    'sessions': []
                                    }
                    return session_list

            if a.getElementsByTagName('Track'):
                session_data = a.getElementsByTagName('Track')
                session_type = 'track'
                logger.debug(u"Track session active.")
                for session in session_data:
                    session_output = self.get_session_each(session_type, session)
                    session_list.append(session_output)
            if a.getElementsByTagName('Video'):
                session_data = a.getElementsByTagName('Video')
                session_type = 'video'
                logger.debug(u"Video session active.")
                for session in session_data:
                    session_output = self.get_session_each(session_type, session)
                    session_list.append(session_output)

        output = {'stream_count': self.get_xml_attr(xml_head[0], 'size'),
                  'sessions': session_list
                  }

        return output

    """
    Return selected data from current sessions.
    This function processes and validates session data

    Parameters required:    stream_type { track or video }
                            session { the session dictionary }
    Output: dict
    """
    def get_session_each(self, stream_type='', session=None):
        session_output = None
        if stream_type == 'track':
            if session.getElementsByTagName('TranscodeSession'):
                transcode_session = session.getElementsByTagName('TranscodeSession')[0]
                audio_decision = self.get_xml_attr(transcode_session, 'audioDecision')
                audio_channels = self.get_xml_attr(transcode_session, 'audioChannels')
                audio_codec = self.get_xml_attr(transcode_session, 'audioCodec')
                duration = self.get_xml_attr(transcode_session, 'duration')
                progress = self.get_xml_attr(transcode_session, 'viewOffset')
            else:
                media_info = session.getElementsByTagName('Media')[0]
                audio_decision = 'direct play'
                audio_channels = self.get_xml_attr(media_info, 'audioChannels')
                audio_codec = self.get_xml_attr(media_info, 'audioCodec')
                duration = self.get_xml_attr(media_info, 'duration')
                progress = self.get_xml_attr(session, 'viewOffset')

            session_output = {'sessionKey': self.get_xml_attr(session, 'sessionKey'),
                              'parentThumb': self.get_xml_attr(session, 'parentThumb'),
                              'thumb': self.get_xml_attr(session, 'thumb'),
                              'user': self.get_xml_attr(session.getElementsByTagName('User')[0], 'title'),
                              'player': self.get_xml_attr(session.getElementsByTagName('Player')[0], 'platform'),
                              'state': self.get_xml_attr(session.getElementsByTagName('Player')[0], 'state'),
                              'artist': self.get_xml_attr(session, 'grandparentTitle'),
                              'album': self.get_xml_attr(session, 'parentTitle'),
                              'track': self.get_xml_attr(session, 'title'),
                              'ratingKey': self.get_xml_attr(session, 'ratingKey'),
                              'audioDecision': audio_decision,
                              'audioChannels': audio_channels,
                              'audioCodec': audio_codec,
                              'duration': duration,
                              'progress': progress,
                              'progressPercent': str(helpers.get_percent(progress, duration)),
                              'type': 'track'
                              }
        elif stream_type == 'video':
            if session.getElementsByTagName('TranscodeSession'):
                transcode_session = session.getElementsByTagName('TranscodeSession')[0]
                audio_decision = self.get_xml_attr(transcode_session, 'audioDecision')
                audio_channels = self.get_xml_attr(transcode_session, 'audioChannels')
                audio_codec = self.get_xml_attr(transcode_session, 'audioCodec')
                video_decision = self.get_xml_attr(transcode_session, 'videoDecision')
                video_codec = self.get_xml_attr(transcode_session, 'videoCodec')
                width = self.get_xml_attr(transcode_session, 'width')
                height = self.get_xml_attr(transcode_session, 'height')
                duration = self.get_xml_attr(session, 'duration')
                progress = self.get_xml_attr(session, 'viewOffset')
            else:
                media_info = session.getElementsByTagName('Media')[0]
                audio_decision = 'direct play'
                audio_channels = self.get_xml_attr(media_info, 'audioChannels')
                audio_codec = self.get_xml_attr(media_info, 'audioCodec')
                video_decision = 'direct play'
                video_codec = self.get_xml_attr(media_info, 'videoCodec')
                width = self.get_xml_attr(media_info, 'width')
                height = self.get_xml_attr(media_info, 'height')
                duration = self.get_xml_attr(media_info, 'duration')
                progress = self.get_xml_attr(session, 'viewOffset')

            if self.get_xml_attr(session, 'type') == 'episode':
                session_output = {'sessionKey': self.get_xml_attr(session, 'sessionKey'),
                                  'art': self.get_xml_attr(session, 'art'),
                                  'thumb': self.get_xml_attr(session, 'thumb'),
                                  'user': self.get_xml_attr(session.getElementsByTagName('User')[0], 'title'),
                                  'player': self.get_xml_attr(session.getElementsByTagName('Player')[0], 'platform'),
                                  'state': self.get_xml_attr(session.getElementsByTagName('Player')[0], 'state'),
                                  'grandparentTitle': self.get_xml_attr(session, 'grandparentTitle'),
                                  'title': self.get_xml_attr(session, 'title'),
                                  'ratingKey': self.get_xml_attr(session, 'ratingKey'),
                                  'audioDecision': audio_decision,
                                  'audioChannels': audio_channels,
                                  'audioCodec': audio_codec,
                                  'videoDecision': video_decision,
                                  'videoCodec': video_codec,
                                  'height': height,
                                  'width': width,
                                  'duration': duration,
                                  'progress': progress,
                                  'progressPercent': str(helpers.get_percent(progress, duration)),
                                  'type': self.get_xml_attr(session, 'type')
                                  }
            elif self.get_xml_attr(session, 'type') == 'movie':
                session_output = {'sessionKey': self.get_xml_attr(session, 'sessionKey'),
                                  'art': self.get_xml_attr(session, 'art'),
                                  'thumb': self.get_xml_attr(session, 'thumb'),
                                  'user': self.get_xml_attr(session.getElementsByTagName('User')[0], 'title'),
                                  'player': self.get_xml_attr(session.getElementsByTagName('Player')[0], 'platform'),
                                  'state': self.get_xml_attr(session.getElementsByTagName('Player')[0], 'state'),
                                  'title': self.get_xml_attr(session, 'title'),
                                  'ratingKey': self.get_xml_attr(session, 'ratingKey'),
                                  'audioDecision': audio_decision,
                                  'audioChannels': audio_channels,
                                  'audioCodec': audio_codec,
                                  'videoDecision': video_decision,
                                  'videoCodec': video_codec,
                                  'height': height,
                                  'width': width,
                                  'duration': duration,
                                  'progress': progress,
                                  'progressPercent': str(helpers.get_percent(progress, duration)),
                                  'type': self.get_xml_attr(session, 'type')
                                  }
        else:
            logger.warn(u"No known stream types found in session list.")

        return session_output

    """
    Return image data as array.
    Array contains the image content type and image binary

    Parameters required:    img { Plex image location }
    Optional parameters:    width { the image width }
                            height { the image height }
    Output: array
    """
    def get_image(self, img, width='0', height='0'):
        if img != '':
            try:
                http_handler = HTTPConnection(self.host, self.port, timeout=10)
                if width != '0' and height != '0':
                    image_path = '/photo/:/transcode?url=http://127.0.0.1:' + self.port + img + '&width=' + width + '&height=' + height
                else:
                    image_path = '/photo/:/transcode?url=http://127.0.0.1:' + self.port + img
                http_handler.request("GET", image_path + '&X-Plex-Token=' + self.token)
                response = http_handler.getresponse()
                request_status = response.status
                request_content = response.read()
                request_content_type = response.getheader('content-type')
                logger.debug(u"Content type: %r" % request_content_type)
            except IOError, e:
                logger.warn(u"Failed to retrieve image. %s" % e)
                return None

        if request_status == 200:
            return [request_content_type, request_content]
        else:
            logger.warn(u"Failed to retrieve image. Status code %r" % request_status)
            return None

        return None
