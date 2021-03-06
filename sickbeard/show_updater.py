# Author: Nic Wolfe <nic@wolfeden.ca>
# URL: http://code.google.com/p/sickbeard/
#
# This file is part of SickGear.
#
# SickGear is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# SickGear is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with SickGear.  If not, see <http://www.gnu.org/licenses/>.

import datetime
import os

import sickbeard

from sickbeard import logger
from sickbeard import exceptions
from sickbeard import ui
from sickbeard.exceptions import ex
from sickbeard import encodingKludge as ek
from sickbeard import db
from sickbeard import network_timezones
from sickbeard import failed_history

class ShowUpdater():
    def __init__(self):
        self.amActive = False

    def run(self, force=False):

        self.amActive = True

        try:
            update_datetime = datetime.datetime.now()
            update_date = update_datetime.date()

            # refresh network timezones
            network_timezones.update_network_dict()

            # update xem id lists
            sickbeard.scene_exceptions.get_xem_ids()

            # update scene exceptions
            sickbeard.scene_exceptions.retrieve_exceptions()

            # sure, why not?
            if sickbeard.USE_FAILED_DOWNLOADS:
                failed_history.trimHistory()

            # clear the data of unused providers
            sickbeard.helpers.clear_unused_providers()

            logger.log(u'Doing full update on all shows')

            # clean out cache directory, remove everything > 12 hours old
            sickbeard.helpers.clearCache()

            # select 10 'Ended' tv_shows updated more than 90 days ago and all shows not updated more then 180 days ago to include in this update
            stale_should_update = []
            stale_update_date = (update_date - datetime.timedelta(days=90)).toordinal()
            stale_update_date_max = (update_date - datetime.timedelta(days=180)).toordinal()

            # last_update_date <= 90 days, sorted ASC because dates are ordinal
            myDB = db.DBConnection()
            sql_results = myDB.mass_action([[
                'SELECT indexer_id FROM tv_shows WHERE last_update_indexer <= ? AND last_update_indexer >= ? ORDER BY last_update_indexer ASC LIMIT 10;',
                [stale_update_date, stale_update_date_max]], ['SELECT indexer_id FROM tv_shows WHERE last_update_indexer < ?;', [stale_update_date_max]]])

            for sql_result in sql_results:
                for cur_result in sql_result:
                    stale_should_update.append(int(cur_result['indexer_id']))

            # start update process
            piList = []
            for curShow in sickbeard.showList:

                try:
                    # get next episode airdate
                    curShow.nextEpisode()

                    # if should_update returns True (not 'Ended') or show is selected stale 'Ended' then update, otherwise just refresh
                    if curShow.should_update(update_date=update_date) or curShow.indexerid in stale_should_update:
                        curQueueItem = sickbeard.showQueueScheduler.action.updateShow(curShow, scheduled_update=True)  # @UndefinedVariable
                    else:
                        logger.log(
                            u'Not updating episodes for show ' + curShow.name + ' because it\'s marked as ended and last/next episode is not within the grace period.',
                            logger.DEBUG)
                        curQueueItem = sickbeard.showQueueScheduler.action.refreshShow(curShow, True, True)  # @UndefinedVariable

                    piList.append(curQueueItem)

                except (exceptions.CantUpdateException, exceptions.CantRefreshException) as e:
                    logger.log(u'Automatic update failed: ' + ex(e), logger.ERROR)

            ui.ProgressIndicators.setIndicator('dailyUpdate', ui.QueueProgressIndicator('Daily Update', piList))

            logger.log(u'Added all shows to show queue for full update')

        finally:
            self.amActive = False

    def __del__(self):
        pass
