# coding=utf-8
import json
import urllib2
import logging

from django.conf import settings
from lxml.etree import Element, SubElement
import requests

from settings import MESSAGES

log = logging.getLogger(__name__)

if hasattr(settings, 'EVMS_URL'):
    EVMS_URL = settings.EVMS_URL
else:
    EVMS_URL = ''


class ValError(Exception):
    """
    An error that occurs during VAL actions.
    This error is raised when the VAL API cannot perform a requested
    action.
    """
    pass


class ValInternalError(ValError):
    """
    An error internal to the VAL API has occurred.
    This error is raised when an error occurs that is not caused by incorrect
    use of the API, but rather internal implementation of the underlying
    services.
    """
    pass


class ValVideoNotFoundError(ValError):
    """
    This error is raised when a video is not found
    If a state is specified in a call to the API that results in no matching
    entry in database, this error may be raised.
    """
    pass


class ValCannotCreateError(ValError):
    """
    This error is raised when an object cannot be created
    """
    pass


def _edx_openedu_compare(openedu_profile, edx_profile, is_studio=False):
    """
    Openedu api возвращает по edx_id url со значениями profile: 'original' и 'hd'.
    EDX для отображения ожидает profile из ['youtube', 'desktop_webm', 'desktop_mp4'].
    Проверяет 'равны' ли значения
    :param openedu_profile:
    :param edx_profile:
    :return:
    """
    mapping = {
        "desktop_mp4": "desktop_mp4",
        "SD": "desktop_webm",
        "sd": "desktop_webm",
        "HD": "desktop_mp4",
        "hd": "desktop_mp4",
        "hd2": "desktop_mp4",
        "audio_sd": "desktop_webm",
        "audio_hd": "desktop_mp4",
    }
    if is_studio:
        mapping['original'] = "desktop_webm"
    if openedu_profile == edx_profile:
        return True
    if openedu_profile in mapping:
        if mapping[openedu_profile] == edx_profile:
            return True
    elif openedu_profile not in ['original', 'mobile']:
        log.warning("Unknown video evms format: {}".format(openedu_profile))
    return False


def get_urls_for_profiles(edx_video_id, val_profiles, is_studio = False):
    raw_data = get_video_info(edx_video_id)
    if raw_data is None:
        raw_data = {}
    profile_data = {}
    sum_len = 0
    for profile in val_profiles:
        url = ''
        if 'encoded_videos' in raw_data:
            videos = raw_data['encoded_videos']
            for video in videos:
                if _edx_openedu_compare(video.get('profile'), profile):
                    url = video.get('url', '')
        profile_data[profile] = url
        sum_len += len(url)
    if sum_len < 1 and is_studio:
        url = ''
        if 'encoded_videos' in raw_data:
            videos = raw_data['encoded_videos']
            for video in videos:
                if _edx_openedu_compare(video.get('profile'), profile, is_studio):
                    url = video.get('url', '')
        profile_data[profile] = url
    return profile_data


def get_url_for_profile(edx_video_id, val_profile):
    return get_urls_for_profiles(edx_video_id, [val_profile])[val_profile]


def get_video_info(edx_video_id):
    if hasattr(settings, 'EVMS_API_KEY'):
        token = getattr(settings, 'EVMS_API_KEY')
    else:
        logging.error("EVMS_API_KEY is not set")
        return None
    url_api = u'{0}/api/v2/video/{1}?token={2}'.format(EVMS_URL, edx_video_id, token)
    try:
        response = requests.get(url_api)
        clean_data = json.loads(response.text)
        return clean_data
    except:
        log.error("EVMS error for url: {}".format(url_api))
        return {'encoded_videos':[]}


def export_to_xml(edx_video_id):
    video = get_video_info(edx_video_id)
    if video is None:
        return Element('video_asset')
    else:
        if isinstance(video, list):
            video = video[0]
    video_el = Element(
        'video_asset',
        attrib={
            'client_video_id': video['client_video_id'],
            'duration': unicode(video['duration']),
        }
    )
    for encoded_video in video['encoded_videos']:
        SubElement(
            video_el,
            'encoded_video',
            {
                name: unicode(encoded_video.get(name))
                for name in ['profile', 'url', 'file_size', 'bitrate']
            }
        )
    # Note: we are *not* exporting Subtitle data since it is not currently updated by VEDA or used
    # by LMS/Studio.
    return video_el


def import_from_xml(xml, edx_video_id, course_id=None):
    return


def get_video_info_for_course_and_profiles(course_id, video_profile_names):
    return {}


def get_course_evms_guid(course_id):
    """
    GUID курса совпадает для разных сессий.
    course_id должен быть в форме org+name+run
    """
    return str(course_id).split('+')[1]


def get_course_edx_val_ids(course_id):
    token = getattr(settings, 'EVMS_API_KEY')
    course_vids_api_url = '{0}/api/v2/course'.format(EVMS_URL)  #только при исполнении, чтобы не было конфликтов при paver update_assets
    course_guid = get_course_evms_guid(course_id)
    url_api = u'{0}/{1}?token={2}'.format(course_vids_api_url, course_guid, token)
    try:
        response = requests.get(url_api)
        videos = response.json().get("videos", False)
    except Exception as e:
        log.error(u"Openedx EVMS api exception: '{}'".format(str(e)))
        return False

    values = [{"display_name": MESSAGES["MANUALLY_MESSAGE"], "value": ""}]
    if not videos:
        log.error(u"EVMS api response error for course_id {} and url {}: {} {}".format(course_guid, url_api, str(response.status_code), response.text))
        return values
    thr = 67 # Длина форматируемой строки для отображения в редакторе Studio
    py_placeholder = " --- "
    for v in videos:
        name = u"{}{}{}".format(v["edx_video_id"], py_placeholder, v["client_video_id"])
        if len(name) > thr:
            name = "".join([name[0:thr], u"..."])
        _dict = {"display_name": name, "value": v["edx_video_id"], "status": v["status"]}
        values.append(_dict)
    return values


def get_available_profiles(edx_video_id, val_profiles):
    """
    Доступные для видео форматы из списка:
        ['original', 'desktop_mp4', 'SD', 'sd', 'HD', 'hd', 'hd2']
    """
    raw_data = get_video_info(edx_video_id)
    if raw_data is None:
        raw_data = []
    profiles = []
    if 'encoded_videos' in raw_data:
        videos = raw_data['encoded_videos']
        for video in videos:
            profiles.append(video["profile"])
    return profiles
