const http = require('http');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const PORT = 8081;
const DIR = __dirname;
const MEETINGS_FILE = path.join(DIR, 'meetings-data.json');
const TEAMMATES_FILE = path.join(DIR, 'teammates.json');

const DEFAULT_TEAMMATES = {
  teammates: [{ id: 'tm-default', name: 'Jaffar H A', email: 'madojamas@gmail.com', asanaGid: '1215117503723367' }]
};

function readJSON(filePath, defaultVal) {
  try { return JSON.parse(fs.readFileSync(filePath, 'utf8')); }
  catch { return defaultVal; }
}

function writeJSON(filePath, data) {
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf8');
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => { try { resolve(JSON.parse(body || '{}')); } catch { resolve({}); } });
    req.on('error', reject);
  });
}

function spawnClaude(prompt) {
  return new Promise((resolve, reject) => {
    const proc = spawn('claude', ['--print', '--output-format', 'text', prompt], {
      shell: true, cwd: DIR, env: process.env
    });
    let out = '', err = '';
    proc.stdout.on('data', d => out += d.toString());
    proc.stderr.on('data', d => err += d.toString());
    proc.on('close', code => code !== 0 ? reject(new Error(err || `exit ${code}`)) : resolve(out.trim()));
    proc.on('error', reject);
    setTimeout(() => { proc.kill(); reject(new Error('claude spawn timed out after 120s')); }, 120000);
  });
}

function extractJSON(text) {
  try { return JSON.parse(text); } catch {}
  const s = text.search(/[\[{]/);
  const e = Math.max(text.lastIndexOf('}'), text.lastIndexOf(']'));
  if (s !== -1 && e !== -1) {
    try { return JSON.parse(text.slice(s, e + 1)); } catch {}
  }
  throw new Error('No JSON found in output: ' + text.slice(0, 300));
}

function json(res, data, status = 200) {
  res.writeHead(status, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
  res.end(JSON.stringify(data));
}

function mergeActionItems(newMeetings, existingMeetings) {
  const existingMap = {};
  for (const m of (existingMeetings || [])) {
    for (const ai of (m.actionItems || [])) {
      existingMap[ai.id] = ai;
    }
  }
  for (const m of newMeetings) {
    for (const ai of (m.actionItems || [])) {
      const prev = existingMap[ai.id];
      if (prev) {
        ai.assigneeId = prev.assigneeId;
        ai.status = prev.status;
        ai.asanaTaskGid = prev.asanaTaskGid;
        ai.pushedAt = prev.pushedAt;
      }
    }
  }
  return newMeetings;
}

const GRANOLA_SYNC_PROMPT = `Use the Granola MCP to pull meeting notes and extract action items. Follow these steps exactly:

1. Call list_meetings with time_range "last_30_days" to get all recent meetings.
2. For each meeting returned, call get_meetings (passing the meeting IDs) to retrieve full notes and content.
3. From each meeting's notes, extract action items. An action item is any of: a bullet point starting with a verb, a sentence containing words like 'will', 'should', 'need to', 'needs to', 'follow up', 'action:', 'TODO', 'next step', or an @mention of a person with a task. Focus on concrete tasks, not discussion points.
4. Return ONLY a raw JSON object (no markdown fences, no explanation, no preamble). The JSON must exactly match this schema:

{"syncedAt":"<ISO timestamp now>","meetings":[{"id":"<meeting id>","title":"<meeting title>","date":"<meeting date ISO>","actionItems":[{"id":"<meetingId>-ai-<0-based index>","text":"<action item text>","meetingId":"<meeting id>","meetingTitle":"<meeting title>","meetingDate":"<meeting date ISO>","assigneeId":null,"status":"unassigned","asanaTaskGid":null,"pushedAt":null}]}]}

Return only the raw JSON. Nothing else.`;

const server = http.createServer(async (req, res) => {
  const url = req.url.split('?')[0];
  const route = `${req.method} ${url}`;

  if (req.method === 'OPTIONS') {
    res.writeHead(204, { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET,POST,OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type' });
    return res.end();
  }

  try {
    if (route === 'GET /') {
      const html = fs.readFileSync(path.join(DIR, 'kanban.html'), 'utf8');
      res.writeHead(200, { 'Content-Type': 'text/html' });
      return res.end(html);
    }

    if (route === 'GET /api/meetings') {
      const data = readJSON(MEETINGS_FILE, { meetings: [], syncedAt: null });
      return json(res, data);
    }

    if (route === 'POST /api/granola/sync') {
      console.log('[granola] spawning claude to sync meetings...');
      let rawOutput;
      try {
        rawOutput = await spawnClaude(GRANOLA_SYNC_PROMPT);
      } catch (err) {
        console.error('[granola] claude spawn failed:', err.message);
        return json(res, { success: false, error: err.message }, 500);
      }
      let parsed;
      try {
        parsed = extractJSON(rawOutput);
      } catch (err) {
        console.error('[granola] JSON parse failed. Raw output:', rawOutput.slice(0, 500));
        return json(res, { success: false, error: 'Could not parse response from Claude', debugOutput: rawOutput.slice(0, 1000) }, 500);
      }
      const existing = readJSON(MEETINGS_FILE, { meetings: [] });
      parsed.meetings = mergeActionItems(parsed.meetings || [], existing.meetings);
      writeJSON(MEETINGS_FILE, parsed);
      const actionItemCount = (parsed.meetings || []).reduce((sum, m) => sum + (m.actionItems || []).length, 0);
      console.log(`[granola] synced ${parsed.meetings.length} meetings, ${actionItemCount} action items`);
      return json(res, { success: true, meetingCount: parsed.meetings.length, actionItemCount });
    }

    if (route === 'GET /api/teammates') {
      const data = readJSON(TEAMMATES_FILE, DEFAULT_TEAMMATES);
      return json(res, data);
    }

    if (route === 'POST /api/teammates') {
      const body = await readBody(req);
      if (!Array.isArray(body.teammates)) return json(res, { success: false, error: 'teammates must be array' }, 400);
      writeJSON(TEAMMATES_FILE, { teammates: body.teammates });
      return json(res, { success: true });
    }

    if (route === 'POST /api/meetings/item') {
      const body = await readBody(req);
      if (!body.id || !body.patch) return json(res, { success: false, error: 'id and patch required' }, 400);
      const data = readJSON(MEETINGS_FILE, { meetings: [] });
      let found = false;
      for (const m of (data.meetings || [])) {
        for (const ai of (m.actionItems || [])) {
          if (ai.id === body.id) {
            Object.assign(ai, body.patch);
            found = true;
            break;
          }
        }
        if (found) break;
      }
      if (!found) return json(res, { success: false, error: 'item not found' }, 404);
      writeJSON(MEETINGS_FILE, data);
      return json(res, { success: true });
    }

    if (route === 'POST /api/asana/push') {
      const body = await readBody(req);
      const { actionItemIds, projectGid } = body;
      if (!Array.isArray(actionItemIds) || !projectGid) {
        return json(res, { success: false, error: 'actionItemIds and projectGid required' }, 400);
      }
      const meetingsData = readJSON(MEETINGS_FILE, { meetings: [] });
      const teammatesData = readJSON(TEAMMATES_FILE, DEFAULT_TEAMMATES);
      const teammateMap = {};
      for (const t of teammatesData.teammates) teammateMap[t.id] = t;

      const itemsToCreate = [];
      for (const m of meetingsData.meetings) {
        for (const ai of (m.actionItems || [])) {
          if (actionItemIds.includes(ai.id)) {
            const assignee = teammateMap[ai.assigneeId];
            itemsToCreate.push({
              actionItemId: ai.id,
              name: ai.text,
              assigneeGid: assignee ? (assignee.asanaGid || null) : null,
              notes: `From meeting: ${ai.meetingTitle} on ${ai.meetingDate ? new Date(ai.meetingDate).toLocaleDateString() : 'unknown date'}`
            });
          }
        }
      }

      if (itemsToCreate.length === 0) return json(res, { success: false, error: 'No matching action items found' }, 400);

      const tasksJSON = JSON.stringify(itemsToCreate);
      const asanaPrompt = `Use the Asana MCP create_tasks tool to create tasks in Asana project GID ${projectGid}. Create one task per item in the array below. For each task use: name from "name" field, assignee from "assigneeGid" (null means unassigned), notes from "notes" field, and project_id "${projectGid}". After ALL tasks are created, return ONLY a raw JSON array (no markdown, no explanation) in this exact format: [{"actionItemId":"<id>","asanaTaskGid":"<created task gid>","success":true}]. One object per task. Tasks to create: ${tasksJSON}`;

      console.log(`[asana] spawning claude to push ${itemsToCreate.length} tasks...`);
      let rawOutput;
      try {
        rawOutput = await spawnClaude(asanaPrompt);
      } catch (err) {
        return json(res, { success: false, error: err.message }, 500);
      }
      let results;
      try {
        results = extractJSON(rawOutput);
      } catch (err) {
        return json(res, { success: false, error: 'Could not parse Asana response', debugOutput: rawOutput.slice(0, 1000) }, 500);
      }
      if (!Array.isArray(results)) results = [results];

      const pushed = [];
      const now = new Date().toISOString();
      for (const r of results) {
        if (r.success) {
          for (const m of meetingsData.meetings) {
            for (const ai of (m.actionItems || [])) {
              if (ai.id === r.actionItemId) {
                ai.status = 'pushed';
                ai.asanaTaskGid = r.asanaTaskGid;
                ai.pushedAt = now;
                pushed.push({ actionItemId: ai.id, asanaTaskGid: r.asanaTaskGid });
              }
            }
          }
        }
      }
      writeJSON(MEETINGS_FILE, meetingsData);
      console.log(`[asana] pushed ${pushed.length} tasks`);
      return json(res, { success: true, pushed });
    }

    res.writeHead(404, { 'Content-Type': 'text/plain' });
    res.end('Not found');
  } catch (err) {
    console.error('[server error]', err);
    json(res, { success: false, error: err.message }, 500);
  }
});

server.listen(PORT, () => {
  console.log(`Kanban server running at http://localhost:${PORT}`);
  console.log(`Open http://localhost:${PORT} in your browser`);
});
