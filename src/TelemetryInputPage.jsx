import React, { useState } from "react";

const TelemetryInputPage = () => {
  const [formData, setFormData] = useState({
    aircraftId: "",
    altitude: "",
    speed: "",
    heading: "",
    latitude: "",
    longitude: "",
    timestamp: "",
  });

  const [entries, setEntries] = useState([]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();

    // Ignore empty aircraft ID
    if (!formData.aircraftId) return;

    setEntries([...entries, formData]);

    setFormData({
      aircraftId: "",
      altitude: "",
      speed: "",
      heading: "",
      latitude: "",
      longitude: "",
      timestamp: "",
    });
  };

  return (
    <div className="min-h-screen bg-gray-100 p-8">
      <div className="max-w-4xl mx-auto bg-white p-6 rounded-2xl shadow-md">
        <h1 className="text-2xl font-bold text-center text-blue-600 mb-6">
          ✈️ Telemetry Input Panel
        </h1>

        {/* Telemetry Form */}
        <form
          onSubmit={handleSubmit}
          className="grid grid-cols-1 md:grid-cols-2 gap-4"
        >
          <div>
            <label className="block text-gray-700 font-medium">
              Aircraft ID
            </label>
            <input
              type="text"
              name="aircraftId"
              value={formData.aircraftId}
              onChange={handleChange}
              className="w-full p-2 border rounded-md focus:outline-none focus:ring focus:ring-blue-300"
              placeholder="e.g. 9W-ABC"
              required
            />
          </div>

          <div>
            <label className="block text-gray-700 font-medium">
              Altitude (ft)
            </label>
            <input
              type="number"
              name="altitude"
              value={formData.altitude}
              onChange={handleChange}
              className="w-full p-2 border rounded-md focus:outline-none focus:ring focus:ring-blue-300"
              placeholder="e.g. 30000"
            />
          </div>

          <div>
            <label className="block text-gray-700 font-medium">
              Speed (knots)
            </label>
            <input
              type="number"
              name="speed"
              value={formData.speed}
              onChange={handleChange}
              className="w-full p-2 border rounded-md focus:outline-none focus:ring focus:ring-blue-300"
              placeholder="e.g. 450"
            />
          </div>

          <div>
            <label className="block text-gray-700 font-medium">
              Heading (deg)
            </label>
            <input
              type="number"
              name="heading"
              value={formData.heading}
              onChange={handleChange}
              className="w-full p-2 border rounded-md focus:outline-none focus:ring focus:ring-blue-300"
              placeholder="e.g. 270"
            />
          </div>

          <div>
            <label className="block text-gray-700 font-medium">Latitude</label>
            <input
              type="number"
              name="latitude"
              value={formData.latitude}
              onChange={handleChange}
              className="w-full p-2 border rounded-md focus:outline-none focus:ring focus:ring-blue-300"
              placeholder="e.g. 28.6139"
            />
          </div>

          <div>
            <label className="block text-gray-700 font-medium">Longitude</label>
            <input
              type="number"
              name="longitude"
              value={formData.longitude}
              onChange={handleChange}
              className="w-full p-2 border rounded-md focus:outline-none focus:ring focus:ring-blue-300"
              placeholder="e.g. 77.2090"
            />
          </div>

          <div className="md:col-span-2">
            <label className="block text-gray-700 font-medium">Timestamp</label>
            <input
              type="datetime-local"
              name="timestamp"
              value={formData.timestamp}
              onChange={handleChange}
              className="w-full p-2 border rounded-md focus:outline-none focus:ring focus:ring-blue-300"
            />
          </div>

          {/* Buttons */}
          <div className="md:col-span-2 flex flex-col md:flex-row gap-4 mt-4 justify-end">
            <button
              type="button"
              className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-xl transition-all shadow-md"
            >
              📡 Fetch Live Telemetry
            </button>

            <button
              type="submit"
              className="bg-green-600 hover:bg-green-700 text-white px-6 py-2 rounded-xl transition-all shadow-md"
            >
              📥 Save Entry
            </button>
          </div>
        </form>

        {/* Telemetry Table */}
        <div className="mt-10">
          <h2 className="text-xl font-semibold text-gray-700 mb-4">
            📜 Telemetry Log Timeline
          </h2>

          <div className="overflow-x-auto">
            <table className="min-w-full bg-white border border-gray-300 rounded-xl shadow-sm">
              <thead className="bg-gray-200 text-gray-700 text-left">
                <tr>
                  <th className="px-4 py-2">Aircraft ID</th>
                  <th className="px-4 py-2">Altitude</th>
                  <th className="px-4 py-2">Speed</th>
                  <th className="px-4 py-2">Heading</th>
                  <th className="px-4 py-2">Lat</th>
                  <th className="px-4 py-2">Long</th>
                  <th className="px-4 py-2">Time</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry, index) => (
                  <tr key={index} className="hover:bg-gray-50">
                    <td className="px-4 py-2">{entry.aircraftId}</td>
                    <td className="px-4 py-2">{entry.altitude}</td>
                    <td className="px-4 py-2">{entry.speed}</td>
                    <td className="px-4 py-2">{entry.heading}</td>
                    <td className="px-4 py-2">{entry.latitude}</td>
                    <td className="px-4 py-2">{entry.longitude}</td>
                    <td className="px-4 py-2">{entry.timestamp}</td>
                  </tr>
                ))}
                {entries.length === 0 && (
                  <tr>
                    <td colSpan="7" className="px-4 py-6 text-center text-gray-400">
                      No entries yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TelemetryInputPage;
