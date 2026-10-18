import Contacts
import UIKit

/// Lo que JARVIS pide hacer en el iPhone: abrir la navegación, llamar, preparar
/// un WhatsApp o lanzar uno de sus Atajos.
enum ClientActions {
    static func url(for action: ClientAction) async -> URL? {
        switch action.type {
        case "navigate":
            return action.url.flatMap { URL(string: $0) }
        case "call":
            guard let name = action.contact, let phone = await phoneNumber(for: name) else { return nil }
            return URL(string: "tel://" + phone.filter { $0.isNumber || $0 == "+" })
        case "send_whatsapp":
            guard let name = action.contact, let phone = await phoneNumber(for: name) else { return nil }
            var components = URLComponents(string: "https://wa.me/" + internationalDigits(phone))
            components?.queryItems = [URLQueryItem(name: "text", value: action.text ?? "")]
            return components?.url
        case "run_shortcut":
            guard let name = action.name else { return nil }
            var components = URLComponents(string: "shortcuts://run-shortcut")
            components?.queryItems = [URLQueryItem(name: "name", value: name)]
            return components?.url
        default:
            return nil
        }
    }

    static func urls(for actions: [ClientAction]) async -> [URL] {
        var result: [URL] = []
        for action in actions {
            if let url = await url(for: action) { result.append(url) }
        }
        return result
    }

    @MainActor
    static func open(_ urls: [URL]) async {
        for url in urls {
            _ = await UIApplication.shared.open(url)
        }
    }

    /// El teléfono del contacto que JARVIS ha nombrado (mejor el móvil).
    static func phoneNumber(for name: String) async -> String? {
        let store = CNContactStore()
        if CNContactStore.authorizationStatus(for: .contacts) == .notDetermined {
            _ = try? await store.requestAccess(for: .contacts)
        }
        let keys = [CNContactPhoneNumbersKey as CNKeyDescriptor]
        let predicate = CNContact.predicateForContacts(matchingName: name)
        guard let contacts = try? store.unifiedContacts(matching: predicate, keysToFetch: keys) else { return nil }
        let mobileLabels = [CNLabelPhoneNumberMobile, CNLabelPhoneNumberiPhone]
        for contact in contacts {
            if let mobile = contact.phoneNumbers.first(where: { mobileLabels.contains($0.label ?? "") }) {
                return mobile.value.stringValue
            }
        }
        return contacts.first?.phoneNumbers.first?.value.stringValue
    }

    /// WhatsApp quiere el número con su prefijo de país y sin «+». Los guardados
    /// sin prefijo se entienden de España (9 cifras) o de Andorra (6 cifras).
    static func internationalDigits(_ phone: String) -> String {
        var digits = phone.filter(\.isNumber)
        if phone.trimmingCharacters(in: .whitespaces).hasPrefix("+") { return digits }
        if digits.hasPrefix("00") {
            digits.removeFirst(2)
            return digits
        }
        if digits.count == 9 { return "34" + digits }
        if digits.count == 6 { return "376" + digits }
        return digits
    }
}
