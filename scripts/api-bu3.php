<?php
/**
 * CassadyNet Poll API
 * Handles poll voting with anti-spam protection
 * 
 * Place this file at: /poll/api.php on your One.com hosting
 */

// Enable CORS for your domain (allow any path on cassadynet.com)
$origin = $_SERVER['HTTP_ORIGIN'] ?? '';
if ($origin === 'https://cassadynet.com' || $origin === 'http://cassadynet.com') {
    header("Access-Control-Allow-Origin: $origin");
} else {
    // Also allow same-origin requests (no Origin header)
    header('Access-Control-Allow-Origin: https://cassadynet.com');
}
header('Access-Control-Allow-Methods: POST, GET, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');
header('Content-Type: application/json');

// Handle preflight
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit();
}

// Database setup
$db_path = __DIR__ . '/polls.db';

function get_db() {
    global $db_path;
    $db = new SQLite3($db_path);
    
    // Create tables if they don't exist
    $db->exec('
        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            poll_id TEXT NOT NULL,
            vote TEXT NOT NULL,
            ip_hash TEXT NOT NULL,
            fingerprint TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ');
    
    $db->exec('
        CREATE TABLE IF NOT EXISTS rate_limits (
            ip_hash TEXT PRIMARY KEY,
            vote_count INTEGER DEFAULT 0,
            first_vote DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_vote DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ');
    
    // Index for faster lookups
    $db->exec('CREATE INDEX IF NOT EXISTS idx_poll_id ON votes(poll_id)');
    $db->exec('CREATE INDEX IF NOT EXISTS idx_ip_hash ON votes(ip_hash)');
    
    return $db;
}

function hash_ip($ip) {
    // Hash IP for privacy but still allows duplicate detection
    return hash('sha256', $ip . 'cassadynet_salt_2024');
}

function get_client_ip() {
    $ip = $_SERVER['REMOTE_ADDR'] ?? '0.0.0.0';
    // Check for forwarded IP (if behind proxy)
    if (!empty($_SERVER['HTTP_X_FORWARDED_FOR'])) {
        $ip = explode(',', $_SERVER['HTTP_X_FORWARDED_FOR'])[0];
    }
    return trim($ip);
}

function check_rate_limit($db, $ip_hash) {
    // Allow max 10 votes per IP per hour, 50 per day
    $stmt = $db->prepare('SELECT vote_count, first_vote, last_vote FROM rate_limits WHERE ip_hash = ?');
    $stmt->bindValue(1, $ip_hash, SQLITE3_TEXT);
    $result = $stmt->execute()->fetchArray(SQLITE3_ASSOC);
    
    if (!$result) {
        return true; // No record, allow
    }
    
    $hourly_limit = 10;
    $daily_limit = 50;
    
    $first_vote = strtotime($result['first_vote']);
    $last_vote = strtotime($result['last_vote']);
    $now = time();
    
    // Reset if first vote was more than 24 hours ago
    if ($now - $first_vote > 86400) {
        $db->exec("DELETE FROM rate_limits WHERE ip_hash = '$ip_hash'");
        return true;
    }
    
    // Check hourly limit (votes in last hour)
    if ($now - $last_vote < 3600 && $result['vote_count'] >= $hourly_limit) {
        return false;
    }
    
    // Check daily limit
    if ($result['vote_count'] >= $daily_limit) {
        return false;
    }
    
    return true;
}

function update_rate_limit($db, $ip_hash) {
    $stmt = $db->prepare('
        INSERT INTO rate_limits (ip_hash, vote_count, first_vote, last_vote) 
        VALUES (?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(ip_hash) DO UPDATE SET 
            vote_count = vote_count + 1,
            last_vote = CURRENT_TIMESTAMP
    ');
    $stmt->bindValue(1, $ip_hash, SQLITE3_TEXT);
    $stmt->execute();
}

function has_voted($db, $poll_id, $ip_hash, $fingerprint = null) {
    // Check by IP hash
    $stmt = $db->prepare('SELECT COUNT(*) as count FROM votes WHERE poll_id = ? AND ip_hash = ?');
    $stmt->bindValue(1, $poll_id, SQLITE3_TEXT);
    $stmt->bindValue(2, $ip_hash, SQLITE3_TEXT);
    $result = $stmt->execute()->fetchArray(SQLITE3_ASSOC);
    
    if ($result['count'] > 0) {
        return true;
    }
    
    // Also check by fingerprint if provided
    if ($fingerprint) {
        $stmt = $db->prepare('SELECT COUNT(*) as count FROM votes WHERE poll_id = ? AND fingerprint = ?');
        $stmt->bindValue(1, $poll_id, SQLITE3_TEXT);
        $stmt->bindValue(2, $fingerprint, SQLITE3_TEXT);
        $result = $stmt->execute()->fetchArray(SQLITE3_ASSOC);
        
        if ($result['count'] > 0) {
            return true;
        }
    }
    
    return false;
}

function cast_vote($db, $poll_id, $vote, $ip_hash, $fingerprint = null) {
    $stmt = $db->prepare('INSERT INTO votes (poll_id, vote, ip_hash, fingerprint) VALUES (?, ?, ?, ?)');
    $stmt->bindValue(1, $poll_id, SQLITE3_TEXT);
    $stmt->bindValue(2, $vote, SQLITE3_TEXT);
    $stmt->bindValue(3, $ip_hash, SQLITE3_TEXT);
    $stmt->bindValue(4, $fingerprint, SQLITE3_TEXT);
    return $stmt->execute();
}

function get_results($db, $poll_id) {
    $stmt = $db->prepare('
        SELECT vote, COUNT(*) as count 
        FROM votes 
        WHERE poll_id = ? 
        GROUP BY vote
    ');
    $stmt->bindValue(1, $poll_id, SQLITE3_TEXT);
    $result = $stmt->execute();
    
    $votes = ['pro' => 0, 'con' => 0];
    while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
        if (isset($votes[$row['vote']])) {
            $votes[$row['vote']] = (int)$row['count'];
        }
    }
    
    $total = $votes['pro'] + $votes['con'];
    
    return [
        'pro' => $votes['pro'],
        'con' => $votes['con'],
        'total' => $total,
        'pro_percent' => $total > 0 ? round(($votes['pro'] / $total) * 100) : 50,
        'con_percent' => $total > 0 ? round(($votes['con'] / $total) * 100) : 50
    ];
}

// Main API logic
try {
    $db = get_db();
    $ip = get_client_ip();
    $ip_hash = hash_ip($ip);
    
    $method = $_SERVER['REQUEST_METHOD'];
    
    if ($method === 'GET') {
        // Get poll results and check if user voted
        $poll_id = $_GET['poll_id'] ?? '';
        
        if (empty($poll_id)) {
            throw new Exception('Missing poll_id');
        }
        
        $fingerprint = $_GET['fingerprint'] ?? null;
        $voted = has_voted($db, $poll_id, $ip_hash, $fingerprint);
        $results = get_results($db, $poll_id);
        
        echo json_encode([
            'success' => true,
            'voted' => $voted,
            'results' => $results
        ]);
        
    } elseif ($method === 'POST') {
        // Cast a vote
        $input = json_decode(file_get_contents('php://input'), true);
        
        $poll_id = $input['poll_id'] ?? '';
        $vote = $input['vote'] ?? '';
        $fingerprint = $input['fingerprint'] ?? null;
        
        if (empty($poll_id) || empty($vote)) {
            throw new Exception('Missing poll_id or vote');
        }
        
        if (!in_array($vote, ['pro', 'con'])) {
            throw new Exception('Invalid vote value');
        }
        
        // Check rate limit
        if (!check_rate_limit($db, $ip_hash)) {
            echo json_encode([
                'success' => false,
                'error' => 'Rate limit exceeded. Please try again later.',
                'voted' => false
            ]);
            exit();
        }
        
        // Check if already voted
        if (has_voted($db, $poll_id, $ip_hash, $fingerprint)) {
            $results = get_results($db, $poll_id);
            echo json_encode([
                'success' => false,
                'error' => 'You have already voted on this poll',
                'voted' => true,
                'results' => $results
            ]);
            exit();
        }
        
        // Cast vote
        cast_vote($db, $poll_id, $vote, $ip_hash, $fingerprint);
        update_rate_limit($db, $ip_hash);
        
        $results = get_results($db, $poll_id);
        
        echo json_encode([
            'success' => true,
            'voted' => true,
            'results' => $results
        ]);
        
    } else {
        throw new Exception('Invalid method');
    }
    
} catch (Exception $e) {
    http_response_code(400);
    echo json_encode([
        'success' => false,
        'error' => $e->getMessage()
    ]);
}
?>
