#!/usr/bin/env python
import calendar
import datetime
import json
import os
import re
import sys

import pyexiv2

DIR_TIMESTAMP_RE = re.compile('(?P<year>\d{4})/(?P<month>\d{2})/(?P<day>\d{2})/'
                              '(?P<hour>\d{2})(?P<min>\d{2})(?P<sec>\d{2})'
                              '\.jpg')


class Error(Exception):
  """base exception class for narrative util functions."""


def UsageError(msg=None):
  print ("""
    Usage:
      ./fix_timestamps.py <narrative_directory> [<utc offset>]

    Example:
      ./fix_timestamps.py /home/user/narrative/ -6
  """)
  if msg:
    print msg
  sys.exit(1)


def GetParsedValidatedArgv(argv):
  if not len(argv) > 1:
    UsageError('Narrative directory is required.')

  if not os.path.isdir(argv[1]):
    UsageError('Path supplied [%s] is not a valid directory.' % argv[1])

  offset = 0
  if len(argv) > 2:
    try:
      offset = int(argv[2])
    except ValueError:
      UsageError('Timezone offset [%s] not an integer.' % argv[2])

  return argv[1], offset


def GetJsonPath(jpg_path):
  dirname, jpg = os.path.split(jpg_path)
  image, _ = os.path.splitext(jpg)
  return os.path.join(dirname, 'meta', image + '.json')


def main(argv):
  narrative_dir, offset = GetParsedValidatedArgv(argv)

  changes = []
  for dirpath, dirnames, filenames in os.walk(argv[1]):
    jpgs = [j for j in filenames if os.path.splitext(j)[1] == '.jpg']
    for jpg in jpgs:
      abspath = os.path.join(dirpath, jpg)
      jsonpath = GetJsonPath(abspath)
      orientation = None
      with open(jsonpath, 'r') as json_file:
        json_data = json.load(json_file)

        # acc_data.samples has three accelerometer values, one for each
        # axis. We can't do much with the Z axis, but X and Y can be
        # used to determine orientation: the axis with the largest absolute
        # value is closest to vertical, and the rotation depends on whether
        # the value is positive or negative. This gets turned into a value
        # from 1-8 per the EXIF "Orientation" field spec.
        #
        # TODO: write a metadata field with the actual degrees of rotation
        #       based on the angle formed by the X and Y values
        acc_data = json_data['acc_data']['samples'][0]
        if abs(acc_data[0]) > abs(acc_data[1]):
          orientation = 1 if acc_data[0] < 0 else 3
        else:
          orientation = 8 if acc_data[1] < 0 else 6

      dir_timestamp = DIR_TIMESTAMP_RE.search(abspath)
      utc_ts = datetime.datetime(int(dir_timestamp.group('year')),
                                 int(dir_timestamp.group('month')),
                                 int(dir_timestamp.group('day')),
                                 int(dir_timestamp.group('hour')),
                                 int(dir_timestamp.group('min')),
                                 int(dir_timestamp.group('sec')))
      local_ts = utc_ts + datetime.timedelta(hours=offset)

      metadata = pyexiv2.ImageMetadata(abspath)
      try:
        metadata.read()
        # TODO(codexile): flag to force even if metadata exists
        should_write = False

        if 'Exif.Image.Orientation' not in metadata:
          metadata['Exif.Image.Orientation'] = orientation
          should_write = True
        if 'Exif.Image.DateTime' not in metadata:
          metadata['Exif.Image.DateTime'] = local_ts
          should_write = True
        if should_write:
          metadata.write()
          timestamp = calendar.timegm(utc_ts.timetuple())
          os.utime(abspath, (timestamp, timestamp))
      except IOError:
        print 'Problem modifying EXIF data for %s.  File corrupt?' % filename

  print 'Done!'


if __name__ == '__main__':
  main(sys.argv)
