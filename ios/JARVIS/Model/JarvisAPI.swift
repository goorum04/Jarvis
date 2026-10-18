import CoreLocation
import Foundation

/// Lo que JARVIS pide hacer en el iPhone tras responder (ver /api/ask).
struct ClientAction: Decodable {
    let type: String
    let destination: String?
    let url: String?
    let contact: String?
    let text: String?
    let name: String?
}

struct AskResponse: Decodable {
    let text: String
    let audio: String?
    let expectsReply: Bool
    let clientActions: [ClientAction]

    enum CodingKeys: String, CodingKey {
        case text, audio
        case expectsReply = "expects_reply"
        case clientActions = "client_actions"
    }
}

struct SpokenResponse: Decodable {
    let text: String
    let audio: String?
}

enum JarvisError: LocalizedError, CustomLocalizedStringResourceConvertible {
    case notPaired, unauthorized, unreachable, server(String)

    var errorDescription: String? {
        switch self {
        case .notPaired:
            return "JARVIS no está conectado. Abre la app y escanea el código de tu panel."
        case .unauthorized:
            return "El acceso a JARVIS ya no vale. Vuelve a escanear el código de tu panel."
        case .unreachable:
            return "JARVIS no responde: su Mac está cerrado, apagado o sin internet."
        case .server(let message):
            return message
        }
    }

    // Lo que dice Siri si falla algo.
    var localizedStringResource: LocalizedStringResource {
        LocalizedStringResource(stringLiteral: errorDescription ?? "Algo ha fallado.")
    }
}

/// Habla con el JARVIS del Mac, con el mismo acceso que el panel y los Atajos.
enum JarvisAPI {
    private struct Detail: Decodable { let detail: String? }

    static func send(
        _ path: String, method: String = "GET", query: [URLQueryItem] = [],
        body: [String: Any]? = nil, timeout: TimeInterval = 90
    ) async throws -> Data {
        guard let pairing = Pairing.current(),
              var components = URLComponents(url: pairing.baseURL.appendingPathComponent(path), resolvingAgainstBaseURL: false)
        else { throw JarvisError.notPaired }
        if !query.isEmpty { components.queryItems = query }
        guard let url = components.url else { throw JarvisError.notPaired }

        var request = URLRequest(url: url, timeoutInterval: timeout)
        request.httpMethod = method
        request.setValue("Bearer \(pairing.token)", forHTTPHeaderField: "Authorization")
        if let body {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
        }

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await URLSession.shared.data(for: request)
        } catch {
            throw JarvisError.unreachable
        }
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        if status == 401 { throw JarvisError.unauthorized }
        if status >= 400 {
            let detail = (try? JSONDecoder().decode(Detail.self, from: data))?.detail
            throw JarvisError.server(detail ?? "JARVIS ha tenido un problema (\(status)). Inténtalo de nuevo.")
        }
        return data
    }

    static func ask(_ text: String, location: CLLocation?) async throws -> AskResponse {
        var body: [String: Any] = ["text": text]
        if let location {
            body["lat"] = location.coordinate.latitude
            body["lon"] = location.coordinate.longitude
        }
        let data = try await send("api/ask", method: "POST", body: body)
        return try JSONDecoder().decode(AskResponse.self, from: data)
    }

    static func greeting(location: CLLocation?) async throws -> SpokenResponse {
        var query: [URLQueryItem] = []
        if let location {
            query = [URLQueryItem(name: "lat", value: String(location.coordinate.latitude)),
                     URLQueryItem(name: "lon", value: String(location.coordinate.longitude))]
        }
        let data = try await send("api/carplay/greeting", query: query)
        return try JSONDecoder().decode(SpokenResponse.self, from: data)
    }

    /// Al bajarse del coche: JARVIS comprueba al minuto si quedó cerrado.
    static func carLeft() async throws {
        _ = try await send("api/car/left", method: "POST", timeout: 20)
    }

    /// Lo mismo que muestra el panel (agenda, correo, coche, WHOOP…), para el arranque.
    static func dashboard() async throws -> [String: Any] {
        let data = try await send("api/dashboard", timeout: 12)
        return (try JSONSerialization.jsonObject(with: data) as? [String: Any]) ?? [:]
    }

    static func registerPush(deviceToken: String, environment: String) async throws {
        _ = try await send("api/push/apns", method: "POST",
                           body: ["device_token": deviceToken, "environment": environment, "device": "iPhone"],
                           timeout: 20)
    }
}
