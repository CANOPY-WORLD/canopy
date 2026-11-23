import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createHash} from 'node:crypto';
import {CARS, PITCH, clockText, createServiceClock, headDistance, peakTrains, preparePatterns, trainsAt, visibleInterval} from '../site/viewer/3d/tube-timetable.mjs';

// A straight 1 km path with three calls; whole-minute times as in the feed.
const schedule = {patterns: [{id: 'p', line: 'demo', path: [[0, 0, -20], [1000, 0, -20]], station_offsets_m: [100, 500, 900]}],
  trips: [{id: 'a', pattern: 'p', times: [[600, 600], [660, 720], [780, 780]], domain_enter_s: 590, domain_exit_s: 800},
          {id: 'b', pattern: 'p', times: [[780, 780], [780, 780], [840, 840]], domain_enter_s: null, domain_exit_s: null}]};
const patterns = preparePatterns(schedule);

test('a train stands during a call and moves linearly between calls', () => {
  const P = patterns.get('p'), times = schedule.trips[0].times;
  assert.equal(headDistance(P, times, 569), null);
  assert.equal(headDistance(P, times, 570), 100);
  assert.equal(headDistance(P, times, 630), 300);
  assert.equal(headDistance(P, times, 690), 500);
  assert.equal(headDistance(P, times, 750), 700);
  assert.equal(headDistance(P, times, 810), 900);
  assert.equal(headDistance(P, times, 811), null);
});
test('six cars trail the head and the domain interval is closed', () => {
  assert.equal(trainsAt(patterns, schedule.trips, 589.9).length, 0);
  const [train] = trainsAt(patterns, schedule.trips, 590);
  assert.equal(train.id, 'a'); assert.equal(train.cars.length, CARS);
  assert.deepEqual(train.cars[0], [100 - PITCH / 2, 0, -20, 0]);
  assert.equal(trainsAt(patterns, schedule.trips, 800).filter(t => t.id === 'a').length, 1);
  assert.equal(trainsAt(patterns, schedule.trips, 800.1).filter(t => t.id === 'a').length, 0);
});
test('a zero-minute run is kept: the head is at the next station in the same second', () => {
  const P = patterns.get('p'), times = schedule.trips[1].times;
  assert.equal(headDistance(P, times, 780), 100);
  assert(Math.abs(headDistance(P, times, 780.001) - (500 + (0.001 / 60) * 400)) < 1e-9);   // 400 m further within a millisecond
});
test('the peak is an exact sweep of closed visibility intervals', () => {
  assert.deepEqual(visibleInterval(schedule.trips[0], 0, 1e6), [590, 800]);
  assert.deepEqual(visibleInterval(schedule.trips[1], 0, 1e6), [750, 870]);
  assert.equal(visibleInterval(schedule.trips[1], 0, 700), null);
  const peak = peakTrains(patterns, schedule.trips, 0, 1e6);
  assert.deepEqual(peak.network, {trains: 2, first_t_s: 750});
  assert.equal(peakTrains(patterns, schedule.trips, 800, 1e6).network.trains, 2);   // both drawn at exactly 800 s
  assert.equal(peakTrains(patterns, schedule.trips, 800.5, 1e6).network.trains, 1);
  for (let t = 560; t <= 880; t += 0.5) assert(trainsAt(patterns, schedule.trips, t).length <= peak.network.trains);
});
test('the service clock is bounded, holds while paused, stops at the end and restarts on Play', () => {
  const clock = createServiceClock({start: 28800, end: 32400});
  assert.equal(clock.time, 28800); assert.equal(clock.playing, false); assert.equal(clock.speed, 30);
  assert.equal(clock.tick(1), false); assert.equal(clock.time, 28800);
  clock.toggle(); assert.equal(clock.tick(1), true); assert.equal(clock.time, 28830);
  clock.toggle(); clock.tick(5); assert.equal(clock.time, 28830);
  clock.seek(1); assert.equal(clock.time, 28800); clock.seek(40000); assert.equal(clock.time, 32400); assert.equal(clock.playing, false);
  clock.seek(32399); clock.toggle(); clock.speed = 60; clock.tick(1); assert.equal(clock.time, 32400); assert.equal(clock.playing, false);
  clock.toggle(); assert.equal(clock.time, 28800); assert.equal(clock.playing, true);
  assert.equal(clockText(30144), '08:22:24');
  assert.throws(() => createServiceClock({start: 5, end: 5}));
});

// The archived AM timetable is published data, not part of this repository. Point CANOPY_TUBE_TIMETABLE at
// underground_trains_am_peak.json to check the rule against it; without it these cases are reported as skipped.
const DATA = process.env.CANOPY_TUBE_TIMETABLE, SHA256 = '0ce2681a7e3c4b9c1baac0aa182d40f41bada31571bd2b58183b93964069cc64';
const WITNESSES = [{"t": 28800, "count": 90, "lines": {"bakerloo": 14, "central": 15, "circle": 8, "district": 18, "hammersmith-city": 4, "jubilee": 7, "metropolitan": 4, "piccadilly": 15, "victoria": 5}, "car": [1184.692978, -1347.073755, -14.493861, -0.334171]}, {"t": 28910, "count": 88, "lines": {"bakerloo": 13, "central": 14, "circle": 8, "district": 18, "hammersmith-city": 4, "jubilee": 7, "metropolitan": 5, "piccadilly": 14, "victoria": 5}, "car": [1806.666973, -1376.311209, -21.391511, 0.011515]}, {"t": 29155, "count": 88, "lines": {"bakerloo": 12, "central": 14, "circle": 7, "district": 19, "hammersmith-city": 4, "jubilee": 8, "metropolitan": 5, "piccadilly": 14, "victoria": 5}, "car": [3181.897933, -423.238262, 0.97487, 0.231179]}, {"t": 30144, "count": 98, "lines": {"bakerloo": 12, "central": 18, "circle": 7, "district": 19, "hammersmith-city": 4, "jubilee": 10, "metropolitan": 7, "piccadilly": 15, "victoria": 6}, "car": null}, {"t": 30600, "count": 92, "lines": {"bakerloo": 13, "central": 17, "circle": 8, "district": 18, "hammersmith-city": 4, "jubilee": 8, "metropolitan": 4, "piccadilly": 15, "victoria": 5}, "car": null}, {"t": 32399, "count": 94, "lines": {"bakerloo": 13, "central": 17, "circle": 8, "district": 19, "hammersmith-city": 5, "jubilee": 7, "metropolitan": 5, "piccadilly": 15, "victoria": 5}, "car": null}, {"t": 32400, "count": 95, "lines": {"bakerloo": 14, "central": 17, "circle": 8, "district": 19, "hammersmith-city": 5, "jubilee": 7, "metropolitan": 5, "piccadilly": 15, "victoria": 5}, "car": null}];
const PEAK = {"network": {"trains": 98, "first_t_s": 30144.0}, "lines": {"bakerloo": 15, "central": 19, "circle": 9, "district": 20, "hammersmith-city": 5, "jubilee": 10, "metropolitan": 8, "piccadilly": 16, "victoria": 6}};
const TRIP = 'VJ3d1a6e9226c7ba5b11495b68e13f2a06cddf2b31';
test('archived AM timetable: seven service seconds and the instance peak', {skip: DATA ? false : 'CANOPY_TUBE_TIMETABLE is not set'}, () => {
  const bytes = fs.readFileSync(DATA);
  assert.equal(createHash('sha256').update(bytes).digest('hex'), SHA256);
  const sched = JSON.parse(bytes), P = preparePatterns(sched), trips = sched.trips.filter(t => P.has(t.pattern));
  assert.deepEqual([sched.period.start_s, sched.period.end_s], [28800, 32400]);
  for (const w of WITNESSES) {
    const list = trainsAt(P, trips, w.t), lines = {};
    for (const train of list) lines[train.line] = (lines[train.line] ?? 0) + 1;
    assert.equal(list.length, w.count, `trains at ${w.t}`);
    assert.deepEqual(Object.fromEntries(Object.entries(lines).sort()), w.lines, `trains by line at ${w.t}`);
    const car = list.find(train => train.id === TRIP)?.cars[0] ?? null;
    if (w.car) for (let k = 0; k < 4; k++) assert(Math.abs(car[k] - w.car[k]) < 1e-3, `example car at ${w.t}`); else assert.equal(car, null);
  }
  const peak = peakTrains(P, trips, 28800, 32400);
  assert.deepEqual(peak.network, PEAK.network);
  assert.deepEqual(Object.fromEntries(Object.entries(peak.lines).map(([k, v]) => [k, v.trains]).sort()), PEAK.lines);
  assert.equal(peak.network.trains * CARS, 588);
  // No second of the hour, and no instant just after a second, draws more trains than the instance buffers hold.
  for (let t = 28800; t <= 32400; t += 0.5) {
    const lines = {}; for (const train of trainsAt(P, trips, t)) lines[train.line] = (lines[train.line] ?? 0) + 1;
    for (const [line, n] of Object.entries(lines)) assert(n <= peak.lines[line].trains, `${line} at ${t}`);
  }
});
