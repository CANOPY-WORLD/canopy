"""Registered current-city selected walk and explicit conditional physiology."""
from canopy._io import read, digest
from .city_exposure import CityExposure
from .city_physiology import CityPhysiology
from healthy_route.city_alignment import Terrain, align_recording
from healthy_route.city_physiology import EstimatedCityFields, evaluate, check_model_coverage
from healthy_route.city_walk import selected_walk
from healthy_route.health_time import HealthReplayFields, time_coverage


class CityWalk(CityPhysiology):
    def validate(self, request, context):
        meta = CityExposure.validate(self, request, context)
        if request['execution'].get('device', 'cpu') != 'cpu':
            raise ValueError('CPU execution required')
        declared = {a['asset'] for a in context.inputs['physiology'][1]['artifacts']}
        required = ['physiology.json']
        if not all(name in declared for name in required):
            raise ValueError('Missing declared physiology input profile')
        from healthy_route.conditional_runtime import read_profile
        read_profile(context.inputs['physiology'][2].parent)
        from healthy_route.inference import load_model
        if read(context.inputs['physiology'][2].parent/'model-identity.json')!=load_model()[3]:raise ValueError('Physiology Asset model identity differs from packaged weights')
        parameters = request['parameters']
        network = read(context.inputs['city'][2].parent / 'network.json')
        if parameters.get('crossing_policy','none')!='none':
            from healthy_route.city_crossings import SOURCE,TRAFFIC
            declared_city={a['asset'] for a in context.inputs['city'][1]['artifacts']}
            if not {SOURCE,TRAFFIC}<=declared_city:raise ValueError('Crossing policy needs pinned source crosswalk tags and current native traffic')
        for key in ['origin', 'goal']:
            if parameters[key] not in network['nodes']:
                raise ValueError('Unknown walking endpoint: ' + key)
        from healthy_route.conditional_runtime import Runtime
        end = time_coverage(meta['fields'], parameters, Runtime.template_horizon_s)['horizon_s']
        if parameters['departure_s'] >= end:
            raise ValueError('Departure is outside the declared Health time coverage')
        if parameters['departure_s'] + parameters['followup_until_elapsed_s'] > end:
            raise ValueError('Follow-up exceeds the declared Health time coverage')
        return meta

    def prepare(self, request, context):
        return (context.inputs['city'][2].parent,
                context.inputs['physiology'][2].parent,
                self.validate(request, context), request['parameters'])

    def execute(self, prepared, context):
        from healthy_route.conditional_runtime import Runtime
        city, physiology, meta, parameters = prepared
        network = read(city / 'network.json')
        crossing_source=None
        if parameters.get('crossing_policy','none')!='none':
            from healthy_route.city_crossings import prepare_crossings,apply_crossing_waits
            network,traffic,crossing_source=prepare_crossings(city,network,context.checkpoint)
        coverage = time_coverage(meta['fields'], parameters, Runtime.template_horizon_s)
        end = coverage['horizon_s']
        route = selected_walk(network, parameters['origin'], parameters['goal'],
                              parameters['speed_m_s'], end - parameters['departure_s'], context.checkpoint)
        if crossing_source is not None:
            route=apply_crossing_waits(route,network,traffic,parameters['departure_s'],end,parameters,context.checkpoint)
        fields = HealthReplayFields(city, meta['fields'], coverage) if coverage['mode']=='health_replay' else EstimatedCityFields(city, meta['fields'])
        fields.estimation_method=parameters.get('spatial_missing_method','nearest')
        terrain = Terrain(read(city / 'scenes/imperial_corridor_8km/context/terrain/terrain.json')['terrain'])
        source = dict(routes=[route, route], departure_s=parameters['departure_s'])
        recording = align_recording(source, network, terrain, fields, context.checkpoint)
        recording.update(alignment=meta['alignment'], inputs=context.request['inputs'],
            temporal_policy=coverage,
            original_timing_preserved=False,
            route_selection=dict(origin=parameters['origin'], goal=parameters['goal'],
                speed_m_s=parameters['speed_m_s'], distance_m=route['distance_m'],
                edge_keys=route['edge_keys'], crossing_ids=route['crossing_ids'],
                method='shortest mapped horizontal distance; no health optimization'),
            signal_status='No traffic signals or clearance shown or used. Crossings use illustrative constant walking speed without signal waits; this is a research route, not navigation advice.',
            missing_policy='Missing native fields remain null. No trajectory gaps are bridged and no city fields are repeated or extrapolated.')
        if crossing_source is not None:
            import copy
            from shapely.geometry import LineString,Point
            recording['route_timeline']=route['timeline']
            recording['crossing_signals']=route['crossing_signals']
            recording['crossing_summary']=dict(wait_s=route['wait_s'],walking_s=route['walking_duration_s'],
                crossing_count=len(route['crossing_signals']),wait_count=len(route['waits']),
                traffic_clock=route['traffic_clock'],provenance=crossing_source,
                assumption='Modelled pedestrian lights at source-tagged crosswalks, including crossings without surveyed signal hardware. Not recorded pedestrian phases or safe-navigation advice.',
                waiting_health='Waiting advances environmental exposure and the CVAE clock at a fixed position. Historical activity/humidity remains the conditional template; no validated resting response is claimed.')
            recording['signal_status']='Modelled pedestrian WAIT/WALK gates plus newer recorded vehicle-gap estimates where lane/clip coverage exists. Elsewhere signals only; vehicle clearance unavailable. Short traffic clip explicitly repeated on the Health clock.'
            recording['alignment']=copy.deepcopy(meta['alignment'])
            recording['alignment']['traffic_clock']=route['traffic_clock']['mapping']
            lines=[LineString([p[:2] for p in e['points']]) for e in route['timeline'] if e.get('crossing_id') and e['kind']!='Waiting']
            heads=[]
            for h in traffic['signals']['heads']:
                if not any(line.distance(Point(h['position'][:2]))<80 for line in lines):continue
                item=copy.deepcopy(h);item['native_position']=h['position']
                x,y,z=h['position'];item['position']=[x,y,terrain.sample(x,y)+z];heads.append(item)
            tls={h['tls'] for h in heads}
            recording['native_vehicle_signals']=dict(heads=heads,timeline={k:v for k,v in traffic['signals']['timeline'].items() if k in tls},recorded_interval=traffic['signals']['recorded_interval'],
                vertical_policy='Health-only display assumption: scene height = pinned terrain + native traffic Z. Native traffic vertical datum is unresolved; this is not validated vertical registration. Original positions retained as native_position')
        folder = physiology
        context.checkpoint()
        policy = {k: v for k, v in parameters.items() if k not in ['origin', 'goal', 'speed_m_s', 'departure_s']}
        check_model_coverage(recording, fields, policy, context.checkpoint)
        runtime = Runtime(folder, seed=42, particles=16, checkpoint=context.checkpoint)
        result = evaluate(recording, fields, runtime, runtime.baseline, policy, context.checkpoint)
        for row in result['samples']:
            if row['phase'] == 'recorded_route':
                row['phase'] = 'calculated_route'
        result['physiology_audit']['inference_input_sha256'] = {p.name: digest(p) for p in folder.iterdir() if p.is_file()}
        result['physiology_inputs'] = context.request['inputs']
        result['physiology_input_kind'] = runtime.input_kind
        result['physiology_audit']['packaged_model'] = runtime.model_manifest
        result['physiology_note'] = ('Synthetic covariate template and assumed reference; no participant data. ' if runtime.input_kind=='synthetic' else 'Locally supplied authorized history; outputs remain private. ') + result['physiology_note']
        result['route_note'] = 'Calculated research walk on the pinned city network. Distance-based routing, not health optimization or recorded human movement.'
        if crossing_source is not None:
            result['route_note']+=f" Includes {route['wait_s']:.1f} s of crossing waits under explicit signal/traffic replay assumptions."
        if coverage['mode']=='health_replay':
            result['route_note'] += ' Health-only repeated pollution and temperature; the shared city retains its native clocks.'
            result['missing_policy'] = 'Native fields remain null outside their source clock or masks. Separately labelled Health inputs repeat the source sequence with bounded donor estimates; no route gaps are bridged.'
            result['physiology_note'] += ' Pollution and temperature use the declared smooth periodic Health replay. This is an extended scenario, not additional measured city data or a forecast; model state and sunlight clocks do not loop with those fields.'
        result['followup_note'] = 'Optional assumed stationary position after calculated arrival. The historical activity template continues; no recovery or recorded movement is claimed.'
        context.emit('progress', completed=len(result['samples']), total=len(result['samples']))
        return {'recording': result, 'diagnostics': {'samples': len(result['samples']),
            'distance_m': route['distance_m'], 'route_duration_s': route['duration_s'],
            **result['physiology_audit'], 'scientific_status': 'conditional research simulation; no clinical or route-safety validation'}}
