const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = 8081;
const DIR = __dirname;
const MEETINGS_FILE = path.join(DIR, 'meetings-data.json');
const TEAMMATES_FILE = path.join(DIR, 'teammates.json');
const ASANA_PENDING_FILE = path.join(DIR, 'asana-pending.json');

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

function json(res, data, status = 200) {
  res.writeHead(status, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
  res.end(JSON.stringify(data));
}


function mergeActionItems(newMeetings, existingMeetings) {
  const existingMap = {};
  for (const m of (existingMeetings || [])) {
    for (const ai of (m.actionItems || [])) existingMap[ai.id] = ai;
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

const server = http.createServer(async (req, res) => {
  const url = req.url.split('?')[0];
  const route = `${req.method} ${url}`;

  if (req.method === 'OPTIONS') {
    res.writeHead(204, { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET,POST,OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type' });
    return res.end();
  }

  try {
    // ── Static ──────────────────────────────────────────────────────────────
    if (route === 'GET /') {
      const html = fs.readFileSync(path.join(DIR, 'kanban.html'), 'utf8');
      res.writeHead(200, { 'Content-Type': 'text/html' });
      return res.end(html);
    }

    // ── Meetings ─────────────────────────────────────────────────────────────
    if (route === 'GET /api/meetings') {
      return json(res, readJSON(MEETINGS_FILE, { meetings: [], syncedAt: null }));
    }

    // Called by Claude (in the Code session) after pulling from Granola MCP
    if (route === 'POST /api/granola/write') {
      const body = await readBody(req);
      if (!body.meetings) return json(res, { success: false, error: 'meetings array required' }, 400);
      const existing = readJSON(MEETINGS_FILE, { meetings: [] });
      body.meetings = mergeActionItems(body.meetings, existing.meetings);
      body.syncedAt = body.syncedAt || new Date().toISOString();
      writeJSON(MEETINGS_FILE, body);
      const count = body.meetings.reduce((s, m) => s + (m.actionItems || []).length, 0);
      console.log(`[granola] wrote ${body.meetings.length} meetings, ${count} action items`);
      return json(res, { success: true, meetingCount: body.meetings.length, actionItemCount: count });
    }

    // ── Teammates ────────────────────────────────────────────────────────────
    if (route === 'GET /api/teammates') {
      return json(res, readJSON(TEAMMATES_FILE, DEFAULT_TEAMMATES));
    }

    if (route === 'POST /api/teammates') {
      const body = await readBody(req);
      if (!Array.isArray(body.teammates)) return json(res, { success: false, error: 'teammates must be array' }, 400);
      writeJSON(TEAMMATES_FILE, { teammates: body.teammates });
      return json(res, { success: true });
    }

    // ── Action item patch ────────────────────────────────────────────────────
    if (route === 'POST /api/meetings/item') {
      const body = await readBody(req);
      if (!body.id || !body.patch) return json(res, { success: false, error: 'id and patch required' }, 400);
      const data = readJSON(MEETINGS_FILE, { meetings: [] });
      let found = false;
      for (const m of (data.meetings || [])) {
        for (const ai of (m.actionItems || [])) {
          if (ai.id === body.id) { Object.assign(ai, body.patch); found = true; break; }
        }
        if (found) break;
      }
      if (!found) return json(res, { success: false, error: 'item not found' }, 404);
      writeJSON(MEETINGS_FILE, data);
      return json(res, { success: true });
    }

    // ── Asana: queue tasks for Claude to push via MCP ────────────────────────
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

      const tasks = [];
      for (const m of meetingsData.meetings) {
        for (const ai of (m.actionItems || [])) {
          if (!actionItemIds.includes(ai.id)) continue;
          const assignee = teammateMap[ai.assigneeId];
          tasks.push({
            actionItemId: ai.id,
            name: ai.text,
            projectGid,
            assigneeGid: assignee?.asanaGid || null,
            assigneeName: assignee?.name || null,
            notes: `From meeting: ${ai.meetingTitle} on ${ai.meetingDate ? new Date(ai.meetingDate).toLocaleDateString() : 'unknown'}`
          });
        }
      }
      writeJSON(ASANA_PENDING_FILE, { tasks, requestedAt: new Date().toISOString() });
      console.log(`[asana] queued ${tasks.length} tasks for Claude to push`);
      return json(res, { success: true, requiresClaude: true, taskCount: tasks.length });
    }

    // Called by Claude after pushing tasks via MCP
    if (route === 'POST /api/asana/complete') {
      const body = await readBody(req);
      if (!Array.isArray(body.pushed)) return json(res, { success: false, error: 'pushed array required' }, 400);
      const meetingsData = readJSON(MEETINGS_FILE, { meetings: [] });
      const now = new Date().toISOString();
      for (const { actionItemId, asanaTaskGid } of body.pushed) {
        for (const m of meetingsData.meetings) {
          for (const ai of (m.actionItems || [])) {
            if (ai.id === actionItemId) {
              ai.status = 'pushed';
              ai.asanaTaskGid = asanaTaskGid;
              ai.pushedAt = now;
            }
          }
        }
      }
      writeJSON(MEETINGS_FILE, meetingsData);
      // Clear the pending file
      try { fs.unlinkSync(ASANA_PENDING_FILE); } catch {}
      console.log(`[asana] marked ${body.pushed.length} tasks as pushed`);
      return json(res, { success: true });
    }

    // Get pending Asana tasks (for Claude to read)
    if (route === 'GET /api/asana/pending') {
      return json(res, readJSON(ASANA_PENDING_FILE, { tasks: [] }));
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
});
