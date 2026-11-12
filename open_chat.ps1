# Waits for the Streamlit server to accept connections, then opens the chat in the
# default browser. Started in the background by run_local_ai_chat.bat.

$port = 8501
$url = "http://localhost:$port"

for ($i = 0; $i -lt 240; $i++) {
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $client.Connect('127.0.0.1', $port)
        $client.Close()
        Start-Sleep -Milliseconds 400
        Start-Process $url
        exit 0
    } catch {
        Start-Sleep -Milliseconds 500
    }
}
Write-Error "Local AI Chat did not start on $url"
exit 1
