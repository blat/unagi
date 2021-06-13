<?php

require __DIR__ . '/vendor/autoload.php';

$config = parse_ini_file(__DIR__ . '/config.ini', true);

//---------------------------------------------------------------------------
// BetaSeries

$betaSeries = new \Betaseries\Client(new \Betaseries\Betaseries($config['betaseries']['api_key'], $config['betaseries']['user_token']));

//---------------------------------------------------------------------------
// RARBG

$torrentApi = new TorrentAPI\TorrentAPI('unagi');

//---------------------------------------------------------------------------
// Transmission

$transmission = new Vohof\Transmission($config['transmission']);

//---------------------------------------------------------------------------
// Addic7ed

$addic7ed = new Alc\Addic7edCli\Database\Addic7edDatabase((new Alc\Addic7edCli\Component\HttpClient())->getClient());

//---------------------------------------------------------------------------
// Init Context

$existingFiles = array_flip(glob($config['unagi']['storage'] . '*/*'));

//---------------------------------------------------------------------------
// Let's go!

foreach ($betaSeries->api('episodes')->lists()['shows'] as $show) {

    $platforms = $betaSeries->api('shows')->display($show['id'])['show']['platforms'];
    $svods = isset($platforms['svods']) ? $platforms['svods'] : [];

    $currentSeason = null;
    foreach ($show['unseen'] as $episode) {
    if ($currentSeason && $currentSeason != $episode['season']) continue;
        $currentSeason = $episode['season'];

        echo "{$episode['show']['title']} {$episode['code']}\n";

        $ready = false;
        foreach ($svods as $svod) {
            if (isset($svod['available']['first']) && $currentSeason < $svod['available']['first']) continue;
            if (isset($svod['available']['last']) && $currentSeason > $svod['available']['last']) continue;

            if (in_array($svod['name'], $config['unagi']['svods'])) {
                echo "-> Do not download {$svod['name']} shows\n";
                $ready = true;
            }
        }

        if (!$ready) {
            $mkv = $config['unagi']['storage'] . $episode['show']['title'] . '/' . $episode['show']['title'] . '.' . $episode['code'] . '.mkv';
            $srt = $config['unagi']['storage'] . $episode['show']['title'] . '/' . $episode['show']['title'] . '.' . $episode['code'] . '.srt';

            unset($existingFiles[$mkv], $existingFiles[$srt]);

            @mkdir(dirname($mkv));

            $hasSrt = false;
            if (file_exists($srt)) {
                $hasSrt = true;
                echo "-> Subtitle already downloaded\n";
            } else {
                $subtitles = $addic7ed->find(sprintf("%s - ", $episode['show']['title']), 'French', $episode['season'], $episode['episode']);
                echo "-> Find " . count($subtitles) . " subtitles\n";
                foreach ($subtitles as $subtitle) {
                    if ($subtitle->completed === 'Completed' || $subtitle->completed === 'Terminé') {
                        echo "-> Download completed subtitle!\n";
                        file_put_contents($srt, file_get_contents($subtitle->url, false, stream_context_create(['http' => [ 'header' => ["Referer: $subtitle->url\r\n"]]])));
                        $hasSrt = true;
                        break;
                    }
                }
                if (!$hasSrt) {
                    echo "-> Subtitle still pending\n";
                }
            }

            $hasMkv = false;
            if (file_exists($mkv)) {
                $hasMkv = true;
                echo "-> Mkv already downloaded\n";
            } else {
                $torrents = $torrentApi->query([
                    'format'        => 'json_extended',
                    'limit'         => 100,
                    'mode'          => 'search',
                    'ranked'        => 0,
                    'search_string' => $episode['code'],
                    'search_tvdb'   => $episode['show']['thetvdb_id'],
                    'sort'          => 'seeders',
                ]);
                if (is_object($torrents) && $torrents->error) {
                    $torrents = [];
                }
                echo "-> Find " . count($torrents) . " torrents\n";
                foreach ($torrents as $torrent) {
                    if (stripos($torrent->title, '720p')) {
                        $result = $transmission->add($torrent->download);
                        if (isset($result['torrent-added'])) {
                            echo "-> Start downloading new torrent\n";
                        } else if (isset($result['torrent-duplicate'])) {
                            $torrentId = $result['torrent-duplicate']['id'];
                            $data = $transmission->get($torrentId)['torrents'][0];
                            if ($data['leftUntilDone'] === 0) {
                                if ($hasSrt) {
                                    echo "-> Torrent completed!\n";
                                    foreach ($data['files'] as $file) {
                                        if (!stripos($file['name'], 'sample') && preg_match('/\.mkv$/', $file['name'])) {
                                            rename($data['downloadDir'] . '/' . $file['name'], $mkv);
                                            $transmission->remove($torrentId, true);
                                            $hasMkv = true;
                                            break;
                                        }
                                    }
                                } else {
                                    echo "-> Torrent ready... wait for subtitle\n";
                                }
                            } else {
                                echo "-> Torrent still pending\n";
                            }
                        }
                        break;
                    }
                }
            }

            $ready = $hasMkv && $hasSrt;
        }

        if ($ready && !$episode['user']['downloaded']) {
            $betaSeries->api('episodes')->downloaded($episode['id']);
        } elseif (!$ready && $episode['user']['downloaded']) {
            $betaSeries->api('episodes')->removeDownloaded($episode['id']);
        }

    }
}

//---------------------------------------------------------------------------
// Cleaning

foreach (array_keys($existingFiles) as $file) {
    $title = basename(dirname($file));
    $result = $betaSeries->api('shows')->search($title);

    $cleaned = false;
    foreach ($result['shows'] as $show) {
        if ($show['title'] == $title && $show['in_account']) {
            $cleaned = true;
            echo "Clean $file\n";
            unlink($file);
        }
    }

    if (!$cleaned) {
        echo "Ignore $file\n";
    }
}
