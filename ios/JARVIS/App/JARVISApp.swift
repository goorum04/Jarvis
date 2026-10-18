import SwiftUI
import UserNotifications

@main
struct JARVISApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var session = Session.shared

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(session)
                .preferredColorScheme(.dark)
                .tint(Theme.accent)
        }
    }
}

/// Los colores y letras de JARVIS: los mismos del panel holográfico.
enum Theme {
    static let background = Color(red: 0.008, green: 0.024, blue: 0.039)
    static let surface = Color(red: 0.035, green: 0.075, blue: 0.110)
    static let accent = Color(red: 0.145, green: 0.784, blue: 0.949)
    static let ice = Color(red: 0.749, green: 0.953, blue: 1.000)
    static let text = Color(red: 0.851, green: 0.925, blue: 0.965)
    static let muted = Color(red: 0.557, green: 0.639, blue: 0.706)
    static let warning = Color(red: 1.000, green: 0.710, blue: 0.278)
    static let alert = Color(red: 1.000, green: 0.302, blue: 0.369)
    static let ok = Color(red: 0.239, green: 0.863, blue: 0.518)

    /// Orbitron (títulos y cifras) y Share Tech Mono (rótulos), incluidas en la app.
    static func display(_ size: CGFloat, weight: Font.Weight = .bold) -> Font {
        .custom("Orbitron", size: size).weight(weight)
    }

    static func mono(_ size: CGFloat) -> Font {
        .custom("ShareTechMono-Regular", size: size)
    }
}

final class AppDelegate: NSObject, UIApplicationDelegate {
    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil
    ) -> Bool {
        UNUserNotificationCenter.current().delegate = PushRegistrar.shared
        _ = LocationProvider.shared  // se crea en el hilo principal, como pide CoreLocation
        PushRegistrar.shared.registerIfAuthorized()
        return true
    }

    func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
        PushRegistrar.shared.didRegister(deviceToken: deviceToken)
    }

    func application(_ application: UIApplication, didFailToRegisterForRemoteNotificationsWithError error: Error) {
        print("JARVIS: sin avisos en este iPhone: \(error.localizedDescription)")
    }
}

/// Avisos de JARVIS en el iPhone: pide permiso, apunta el iPhone en JARVIS y
/// abre lo que traiga el aviso (por ejemplo, la navegación) al tocarlo.
final class PushRegistrar: NSObject, UNUserNotificationCenterDelegate {
    static let shared = PushRegistrar()

    func requestAuthorizationAndRegister() async {
        let granted = (try? await UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge])) ?? false
        if granted {
            await MainActor.run { UIApplication.shared.registerForRemoteNotifications() }
        }
    }

    func registerIfAuthorized() {
        UNUserNotificationCenter.current().getNotificationSettings { settings in
            guard settings.authorizationStatus == .authorized else { return }
            DispatchQueue.main.async { UIApplication.shared.registerForRemoteNotifications() }
        }
    }

    func statusText() async -> String {
        let settings = await UNUserNotificationCenter.current().notificationSettings()
        switch settings.authorizationStatus {
        case .authorized, .provisional, .ephemeral:
            return "Activados"
        case .denied:
            return "Bloqueados: Ajustes → Notificaciones → JARVIS"
        default:
            return "Sin activar"
        }
    }

    func didRegister(deviceToken: Data) {
        let token = deviceToken.map { String(format: "%02x", $0) }.joined()
        #if DEBUG
        let environment = "sandbox"
        #else
        let environment = "production"
        #endif
        Task { try? await JarvisAPI.registerPush(deviceToken: token, environment: environment) }
    }

    // Con la app abierta, el aviso también se enseña arriba.
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification
    ) async -> UNNotificationPresentationOptions {
        [.banner, .list, .sound]
    }

    func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse) async {
        guard let link = response.notification.request.content.userInfo["url"] as? String,
              !link.hasPrefix("/"), let url = URL(string: link), url.scheme != nil
        else { return }
        await MainActor.run { UIApplication.shared.open(url) }
    }
}
