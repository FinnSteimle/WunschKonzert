import http from 'k6/http';
import { check, sleep } from 'k6';

/**
 * k6 Scalability Test for Wunschkonzert NFR WUN-88 Verification
 * 
 * Acceptance Criteria:
 * - Verified for 2,500 users (100 rooms with 25 users each)
 * 
 * Run with: k6 run load-tests/scalability_test_local.js
 */

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const NUM_ROOMS = 100;
const USERS_PER_ROOM = 25;
const TOTAL_USERS = NUM_ROOMS * USERS_PER_ROOM;

export const options = {
  scenarios: {
    scalability: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '2m', target: TOTAL_USERS }, // Ramp up to 2,500 users over 2 minutes
        { duration: '5m', target: TOTAL_USERS }, // Stay at 2,500 for 5 minutes
        { duration: '1m', target: 0 },           // Ramp down
      ],
    },
  },
  thresholds: {
    // Error rate must be below 1%
    'http_req_failed': ['rate<0.01'],
    // 95% of requests should be under 2s under extreme load
    'http_req_duration': ['p(95)<2000'],
  },
  setupTimeout: '10m', // Increase setup timeout for 100 rooms
};

function randomString(length) {
  const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
  let res = '';
  for (let i = 0; i < length; i++) {
    res += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return res;
}

export function setup() {
  const codes = [];
  console.log(`Setting up ${NUM_ROOMS} rooms at ${BASE_URL}...`);
  
  for (let i = 0; i < NUM_ROOMS; i++) {
    const userId = `host-${i}-${randomString(6)}`;
    const displayName = `Host ${i}`;
    
    const params = { headers: { 'Content-Type': 'application/json' } };
    
    // 1. Seed the host user
    const seedPayload = JSON.stringify({
      user_id: userId,
      display_name: displayName
    });
    const seedRes = http.post(`${BASE_URL}/debug/seed_user`, seedPayload, params);
    
    if (seedRes.status !== 200) {
      console.error(`Failed to seed host ${i}: ${seedRes.status}`);
      continue;
    }

    // 2. Create the room
    const payload = JSON.stringify({
      name: `Scale Test Room ${i}`,
      user_id: userId,
      display_name: displayName,
      supported_provider_id: 'spotify' 
    });
    
    const res = http.post(`${BASE_URL}/create_room`, payload, params);
    
    if (res.status === 200) {
      const body = res.json();
      codes.push(body.join_code);
    } else {
      console.error(`Failed to create room ${i}: ${res.status}`);
    }

    if ((i + 1) % 50 === 0) {
      console.log(`Created ${i + 1}/${NUM_ROOMS} rooms...`);
    }
  }
  
  if (codes.length < NUM_ROOMS) {
    console.warn(`Only created ${codes.length}/${NUM_ROOMS} rooms. Continuing anyway.`);
  }
  
  return { codes };
}

export default function (data) {
  const vu = __VU; // 1 to TOTAL_USERS (2,500)
  
  if (vu <= NUM_ROOMS) {
    // --- HOSTS (1 per room) ---
    const roomIdx = vu - 1;
    const joinCode = data.codes[roomIdx];
    
    if (!joinCode) return;

    // Hosts check availability occasionally
    const res = http.post(`${BASE_URL}/rooms/availability`, JSON.stringify({
        join_codes: [joinCode]
    }), { headers: { 'Content-Type': 'application/json' } });
    
    check(res, {
        'host: status is 200': (r) => r.status === 200,
    });

    sleep(10 + Math.random() * 5);
  } else {
    // --- PARTICIPANTS (24 per room) ---
    const participantIdx = vu - NUM_ROOMS - 1;
    const roomIdx = participantIdx % NUM_ROOMS;
    const joinCode = data.codes[roomIdx];
    
    if (!joinCode) return;

    const guestId = `guest-${vu}-${randomString(6)}`;
    
    // 1. Join the room
    const joinRes = http.post(`${BASE_URL}/join_room`, JSON.stringify({
        join_code: joinCode,
        user_id: guestId,
        display_name: `Guest ${vu}`
    }), { headers: { 'Content-Type': 'application/json' } });
    
    const joined = check(joinRes, {
        'guest: joined successfully': (r) => r.status === 200,
    });
    
    if (joined) {
        // 2. Simulate activity: check availability (heartbeat)
        sleep(5 + Math.random() * 20);
        
        http.post(`${BASE_URL}/rooms/availability`, JSON.stringify({
            join_codes: [joinCode]
        }), { headers: { 'Content-Type': 'application/json' } });
    }
    
    sleep(15 + Math.random() * 10);
  }
}
