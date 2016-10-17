# -*- coding: utf-8 -*-
import googlemaps
from raspysystem.raspytask import RasPyTask
from raspysystem.raspysamplelogger import RasPySampleLogger
from raspysystem.raspyenergymeter import RasPyEnergyMeter

class Route(object):

    def __init__(self, deptime, route):

        self._timestamp = deptime.jstimestamp()
        self._bounds = route["bounds"]
        self._polyline = route["overview_polyline"]["points"]

        # assume no waypoints in this route
        leg0 = route["legs"][0]
        self._start = leg0["start_address"]
        self._end = leg0["end_address"]
        self._start_location = leg0["start_location"]
        self._end_location = leg0["end_location"]
        self._distance = leg0["distance"]["value"]
        self._duration = leg0["duration"]["value"]

        self._arrival_time = None
        if "arrival_time" in leg0:
            self._arrival_time = leg0["arrival_time"]["value"]

        self._departure_time = None
        if "departure_time" in leg0:
            self._departure_time = leg0["departure_time"]["value"]

        self._duration_traffic = None
        if "duration_in_traffic" in leg0:
            self._duration_traffic = leg0["duration_in_traffic"]["value"]

        # parse steps
        self._steps = list()
        for step in leg0["steps"]:
            step["distance"] = step["distance"]["value"]
            step["duration"] = step["duration"]["value"]
            step.pop("end_location", None)
            step.pop("start_location", None)
            step.pop("polyline", None)

            if step["travel_mode"] == "TRANSIT":
                td = step["transit_details"]
                td["arrival_stop"] = td["arrival_stop"]["name"]
                td["departure_stop"] = td["departure_stop"]["name"]
                td["arrival_time"] = td["arrival_time"]["value"]
                td["departure_time"] = td["departure_time"]["value"]
                td["line"] = td["line"]["short_name"]
                step["transit_details"] = td

            self._steps.append(step)

    def serialize(self):
        return dict(
            bounds=self._bounds,
            polyline=self._polyline,
            start=self._start,
            end=self._end,
            start_location=self._start_location,
            end_location=self._end_location,
            distance=self._distance,
            duration=self._duration,
            duration_traffic=self._duration_traffic,
            arrival_time=self._arrival_time,
            departure_time=self._departure_time,
            steps=self._steps
        )

class Direction(object):
    MODE_DRIVING = 0x01
    MODE_TRANSIT = 0x02
    MODE_BIKEING = 0x04
    MODE_WALKING = 0x08

    def __init__(self, placeFrom, placeTo, dirMode):
        self._from = placeFrom
        self._to = placeTo
        self._mode = dirMode
        self._routes_driving = list()
        self._routes_transit = list()

    def update_routes(self, routes):
        self._routes_driving = routes["driving"]
        self._routes_transit = routes["transit"]

    def equal(self, other):
        return (
            other.is_from(self._from) and
            other.is_to(self._to) and
            other.is_mode(self._mode)
        )

    def is_from(self, placeFrom):
        return self._from == placeFrom

    def is_to(self, placeTo):
        return self._to == placeTo

    def is_mode(self, dirMode):
        return self._mode == dirMode

    def get_mode(self):
        return self._mode

    def get_to(self):
        return self._to

    def get_from(self):
        return self._from

    def serialize(self):
        return dict(
            placeFrom=self._from,
            placeTo=self._to,
            mode=self._mode,
            routes=dict(
                driving=[
                    None if r is None else r.serialize()
                    for r in self._routes_driving
                ],
                transit=[
                    None if r is None else r.serialize()
                    for r in self._routes_transit
                ]
            )
        )

class TrafficTask(RasPyTask):


    def __init__(self, parent):
        RasPyTask.__init__(self, parent, "traffic")

        self._gmaps = None
        self._updates = 0
        self._synctime = None
        self._directions = list()

    def run_event(self):
        time = self.time()

        # every 15min
        if not time.every_quarter() and (self._updates!=0):
            return True

        # for each destination
        for di in self._directions:

            # add default values
            routes = dict(
                driving=list(),
                transit=list()
            )
            route_lookahead = dict(
                # lookahead 15min
                driving=[15],
                # lookahead 15min and 30min
                transit=[15, 30]
            )

            # if one fails, stop request for all
            # ok we got default values
            try:
                for mode in routes:
                    if(
                        (
                            mode == "driving" and
                            (di.get_mode() & Direction.MODE_DRIVING == 0)
                        ) or
                        (
                            mode == "transit" and
                            (di.get_mode() & Direction.MODE_TRANSIT == 0)
                        )
                    ):
                        continue

                    for minute in route_lookahead[mode]:
                        deptime = time.replace(minutes=+minute)
                        routes_found = self._gmaps.directions(
                            "place_id:{}".format(di.get_from()),
                            "place_id:{}".format(di.get_to()),
                            mode=mode,
                            language="de",
                            units="metric",
                            alternatives=True,
                            departure_time=deptime.timestamp
                        )
                        # number of routes can be zero
                        for route in routes_found:
                            # we request no waypoints, so cnt(legs)===1
                            if len(route["legs"]) != 1:
                                self.loge("Invalid number of legs")
                                continue
                            routes[mode].append(
                                Route(time, route)
                            )

            except googlemaps.exceptions.TransportError as e:
                self.loge("Error Transport: {}".format(e))
            except googlemaps.exceptions.HTTPError as e:
                self.loge("Error HTTP: {}".format(e))
            except googlemaps.exceptions.APIError as e:
                self.loge("Error API: {}".format(e))
            except googlemaps.exceptions.Timeout:
                self.loge("Timout occured")

            di.update_routes(routes)

        self._updates += 1
        self._synctime = time.jstimestamp()
        return True

    def report_event(self):
        return dict(
            updates=self._updates,
            synctime=self._synctime,
            directions=[d.serialize() for d in self._directions]
        )

    def startup_event(self, db, cfg):

        if not self._config_expect(
            ["apikey"], cfg
        ):
            return False

        try:
            self._gmaps = googlemaps.Client(
                key=cfg["apikey"],
                timeout=self.kernel().get_timeout(),
                retry_timeout=self.kernel().get_timeout()
            )
        except ValueError:
            self.loge("The apikey is invalid")
            return False

        # create tables if not exist
        db.execute(
            "CREATE TABLE IF NOT EXISTS '{}' ({}, {}, {}, {})".format(
                "traffic_places",
                "'id' INTEGER PRIMARY KEY",
                "'from' TEXT",
                "'to' TEXT",
                "'mode' INTEGER"
            )
        )

        # read rest from database
        db.execute("SELECT * FROM traffic_places")

        for r in db.fetchall():
            placeFrom = r["from"]
            placeTo = r["to"]
            dirMode = int(r["mode"])

            newdir = Direction(placeFrom, placeTo, dirMode)
            # check name
            for storeddir in self._directions:
                if storeddir.equal(newdir):
                    self.loge("Direction is already stored")
                    return False
            self._directions.append(newdir)
        return True
