module.exports = async function handler(req, res) {
  // Set CORS headers
  res.setHeader('Access-Control-Allow-Credentials', 'true');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,OPTIONS,POST');
  res.setHeader(
    'Access-Control-Allow-Headers',
    'X-CSRF-Token, X-Requested-With, Accept, Accept-Version, Content-Length, Content-MD5, Content-Type, Date, X-Api-Version'
  );

  if (req.method === 'OPTIONS') {
    res.status(200).end();
    return;
  }

  // Support both GET query and POST body
  const startX = req.query?.startX || req.body?.startX;
  const startY = req.query?.startY || req.body?.startY;
  const endX = req.query?.endX || req.body?.endX;
  const endY = req.query?.endY || req.body?.endY;

  if (!startX || !startY || !endX || !endY) {
    return res.status(400).json({ error: 'Missing coordinates (startX, startY, endX, endY)' });
  }

  const appKey = process.env.TMAP_APP_KEY || 'iK60UGHNRY4v9vNaGNgMz3B4H8zWKyQi70J0FzDL';

  try {
    const url = `https://apis.openapi.sk.com/tmap/routes/pedestrian?version=1&appKey=${encodeURIComponent(appKey)}`;
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        startX: Number(startX),
        startY: Number(startY),
        endX: Number(endX),
        endY: Number(endY),
        reqCoordType: 'WGS84GEO',
        resCoordType: 'WGS84GEO',
        startName: '출발지',
        endName: '도착지',
      }),
    });

    if (!response.ok) {
      const errText = await response.text();
      console.error('TMAP API error:', response.status, errText);
      return res.status(response.status).json({ error: 'TMAP API failed', details: errText });
    }

    const data = await response.json();
    const path = [];
    let totalDistance = 0;
    let totalTime = 0;

    if (data.features && data.features.length > 0) {
      totalDistance = data.features[0].properties?.totalDistance || 0;
      totalTime = data.features[0].properties?.totalTime || 0;

      for (const feature of data.features) {
        if (feature.geometry?.type === 'LineString') {
          for (const coord of feature.geometry.coordinates) {
            // TMAP returns [longitude, latitude]
            path.push({
              lat: coord[1],
              lng: coord[0],
            });
          }
        }
      }
    }

    // Set cache headers (cache for 1 hour at edge)
    res.setHeader('Cache-Control', 's-maxage=3600, stale-while-revalidate=600');

    return res.status(200).json({
      status: 'OK',
      totalDistance,
      totalTime,
      path,
    });
  } catch (error) {
    console.error('Serverless function error:', error);
    return res.status(500).json({ error: 'Internal Server Error', message: error.message });
  }
};
