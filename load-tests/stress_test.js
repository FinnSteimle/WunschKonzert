import http from 'k6/http';
import { check, sleep } from 'k6';

/**
 * k6 Load Test for Wunschkonzert NFR Verification
 * 
 * Verifies:
 * - WUN-87: Minimum Capacity (100 concurrent users across 10 rooms)
 * - WUN-83: Time Behavior (API response < 500ms)
 * 
 * Run with: k6 run load-tests/stress_test.js
 */

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

export const options = {
  scenarios: {
    stress: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '10s', target: 100 }, // Ramp up to 100 users
        { duration: '20s', target: 100 }, // Stay at 100 for 20s
        { duration: '5s', target: 0 },   // Ramp down
      ],
    },
  },
  thresholds: {
    // p(95) response time must be below 500ms (NFR WUN-83)
    'http_req_duration{scenario:stress}': ['p(95)<500'],
    // Error rate must be below 1% (NFR WUN-87)
    'http_req_failed': ['rate<0.01'],
  },
};

function randomString(length) {
  const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
  let res = '';
  for (let i = 0; i < length; i++) {
    res += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return res;
}

// setup() runs once at the beginning to prepare the test data (the 10 rooms)
export function setup() {
  const codes = [];
  console.log(`Setting up 10 rooms at ${BASE_URL}...`);
  
  for (let i = 0; i < 10; i++) {
    const userId = `host-${i}-${randomString(6)}`;
    const displayName = `Host ${i}`;
    
    const params = { headers: { 'Content-Type': 'application/json' } };
    
    // 1. Seed the host user with mock Spotify tokens (to bypass 403)
    const seedPayload = JSON.stringify({
      user_id: userId,
      display_name: displayName
    });
    const seedRes = http.post(`${BASE_URL}/debug/seed_user`, seedPayload, params);
    
    if (seedRes.status !== 200) {
      console.error(`Failed to seed host ${i}: ${seedRes.status} ${seedRes.body}`);
      continue;
    }

    // 2. Create the room
    const payload = JSON.stringify({
      name: `Stress Test Room ${i}`,
      user_id: userId,
      display_name: displayName,
      supported_provider_id: 'spotify' 
    });
    
    const res = http.post(`${BASE_URL}/create_room`, payload, params);
    
    if (res.status === 200) {
      const body = res.json();
      codes.push(body.join_code);
      console.log(`Created room ${i}: ${body.join_code}`);
    } else {
      console.error(`Failed to create room ${i}: ${res.status} ${res.body}`);
    }
  }
  
  if (codes.length < 10) {
    throw new Error(`Only created ${codes.length}/10 rooms. Aborting.`);
  }
  
  return { codes };
}

// default function is executed by each VU (100 total)
export default function (data) {
  const vu = __VU; // 1 to 100
  
  if (vu <= 10) {
    // --- 10 HOSTS ---
    const joinCode = data.codes[vu - 1];
    
    // Hosts simulate activity by checking availability and waiting
    for (let i = 0; i < 3; i++) {
        const res = http.post(`${BASE_URL}/rooms/availability`, JSON.stringify({
            join_codes: [joinCode]
        }), { headers: { 'Content-Type': 'application/json' } });
        
        const isOk = check(res, {
            'host: status is 200': (r) => r.status === 200,
        });

        if (isOk && res.body) {
            check(res, {
                'host: room is available': (r) => r.json().available_join_codes.includes(joinCode)
            });
        }
        sleep(5 + Math.random() * 2);
    }
  } else {
    // --- 90 PARTICIPANTS ---
    // Distribute 9 participants per room (90 / 10 = 9)
    const roomIdx = Math.floor((vu - 1) % 10); // Better distribution for ramping
    const joinCode = data.codes[roomIdx];
    const guestId = `guest-${vu}-${randomString(6)}`;
    
    // 1. Join the room
    const joinRes = http.post(`${BASE_URL}/join_room`, JSON.stringify({
        join_code: joinCode,
        user_id: guestId,
        display_name: `Guest ${vu}`
    }), { headers: { 'Content-Type': 'application/json' } });
    
    const joined = check(joinRes, {
        'guest: joined successfully': (r) => r.status === 200,
        'guest: join latency < 500ms': (r) => r.timings.duration < 500,
    });
    
    if (joined) {
        // 2. Simulate staying in the room
        sleep(2 + Math.random() * 8);
        
        // Heartbeat / refresh state
        http.post(`${BASE_URL}/rooms/availability`, JSON.stringify({
            join_codes: [joinCode]
        }), { headers: { 'Content-Type': 'application/json' } });
    }
    
    sleep(1 + Math.random());
  }
}
