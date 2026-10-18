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

/// Los colores de JARVIS: los mismos del panel y del icono.
enum Theme {
    static let background = Color(red: 0.020, green: 0.031, blue: 0.047)
    static let surface = Color(red: 0.051, green: 0.082, blue: 0.118)
    static let accent = Color(red: 0.145, green: 0.784, blue: 0.949)
    static let text = Color(red: 0.851, green: 0.925, blue: 0.965)
    static let muted = Color(red: 0.557, green: 0.639, blue: 0.706)
    static let warning = Color(red: 1.000, green: 0.710, blue: 0.278)
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
