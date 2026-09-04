<?php
$backend = 'http://127.0.0.1:8081';
$path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
$queryString = parse_url($_SERVER['REQUEST_URI'], PHP_URL_QUERY);
$backendUrl = $backend . $path;
if ($queryString) $backendUrl .= '?' . $queryString;

$ch = curl_init($backendUrl);
$method = $_SERVER['REQUEST_METHOD'];
curl_setopt($ch, CURLOPT_CUSTOMREQUEST, $method);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_HEADER, true);
curl_setopt($ch, CURLOPT_TIMEOUT, 30);

$input = file_get_contents('php://input');
if (strlen($input) > 0) {
    curl_setopt($ch, CURLOPT_POSTFIELDS, $input);
}

$headers = [];
foreach (getallheaders() as $name => $value) {
    $lower = strtolower($name);
    if ($lower === 'host' || $lower === 'content-length' || $lower === 'connection') continue;
    $headers[] = "$name: $value";
}
if (!empty($headers)) {
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
}

$response = curl_exec($ch);
$httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
$headerSize = curl_getinfo($ch, CURLINFO_HEADER_SIZE);
$curlError = curl_error($ch);
curl_close($ch);

if ($curlError) {
    header('Content-Type: application/json');
    http_response_code(502);
    echo json_encode(['error' => 'Proxy error: ' . $curlError]);
    exit;
}

$responseHeaders = substr($response, 0, $headerSize);
$responseBody = substr($response, $headerSize);

$skipHeaders = ['transfer-encoding', 'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization', 'te', 'trailers', 'upgrade'];
foreach (explode("\r\n", $responseHeaders) as $header) {
    if (empty($header)) continue;
    $parts = explode(':', $header, 2);
    if (count($parts) === 2) {
        $name = strtolower(trim($parts[0]));
        if (!in_array($name, $skipHeaders)) {
            header($header);
        }
    }
}
http_response_code($httpCode);
echo $responseBody;

