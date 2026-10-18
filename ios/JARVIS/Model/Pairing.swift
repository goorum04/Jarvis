import Foundation
import Security

/// Llavero del iPhone: ahí se guardan la dirección del Mac de JARVIS y su token.
enum Keychain {
    private static let service = "jarvis"

    private static func query(_ key: String) -> [String: Any] {
        [kSecClass as String: kSecClassGenericPassword,
         kSecAttrService as String: service,
         kSecAttrAccount as String: key]
    }

    static func set(_ value: String, for key: String) {
        SecItemDelete(query(key) as CFDictionary)
        var item = query(key)
        item[kSecValueData as String] = Data(value.utf8)
        // Disponible en segundo plano (Siri, CarPlay) una vez desbloqueado tras encender.
        item[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
        SecItemAdd(item as CFDictionary, nil)
    }

    static func get(_ key: String) -> String? {
        var item = query(key)
        item[kSecReturnData as String] = true
        item[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: AnyObject?
        guard SecItemCopyMatching(item as CFDictionary, &result) == errSecSuccess,
              let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    static func delete(_ key: String) {
        SecItemDelete(query(key) as CFDictionary)
    }
}

/// Con qué JARVIS habla esta app. Sale del QR del panel (Conexiones → Tu iPhone),
/// que es el enlace del panel con su acceso: https://….ts.net/?token=…
struct Pairing: Equatable {
    let baseURL: URL
    let token: String

    static func current() -> Pairing? {
        guard let base = Keychain.get("baseURL"), let url = URL(string: base),
              let token = Keychain.get("token"), !token.isEmpty else { return nil }
        return Pairing(baseURL: url, token: token)
    }

    static func parse(_ text: String) -> Pairing? {
        guard let components = URLComponents(string: text.trimmingCharacters(in: .whitespacesAndNewlines)),
              components.scheme?.lowercased() == "https",
              let host = components.host, !host.isEmpty,
              let token = components.queryItems?.first(where: { $0.name == "token" })?.value, !token.isEmpty
        else { return nil }
        var base = URLComponents()
        base.scheme = "https"
        base.host = host
        base.port = components.port
        guard let url = base.url else { return nil }
        return Pairing(baseURL: url, token: token)
    }

    func save() {
        Keychain.set(baseURL.absoluteString, for: "baseURL")
        Keychain.set(token, for: "token")
    }

    static func clear() {
        Keychain.delete("baseURL")
        Keychain.delete("token")
    }

    /// El panel en Safari, ya con su acceso.
    var panelURL: URL? {
        var components = URLComponents(url: baseURL, resolvingAgainstBaseURL: false)
        components?.path = "/"
        components?.queryItems = [URLQueryItem(name: "token", value: token)]
        return components?.url
    }
}

@MainActor
final class Session: ObservableObject {
    static let shared = Session()

    @Published private(set) var pairing: Pairing? = Pairing.current()

    func pair(with text: String) -> Bool {
        guard let pairing = Pairing.parse(text) else { return false }
        pairing.save()
        self.pairing = pairing
        PushRegistrar.shared.registerIfAuthorized()
        return true
    }

    func unpair() {
        Pairing.clear()
        pairing = nil
    }
}
