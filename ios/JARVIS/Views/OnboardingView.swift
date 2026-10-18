import AVFoundation
import SwiftUI
import VisionKit

/// Primera vez: se conecta la app con el JARVIS del Mac escaneando el QR del
/// panel (Conexiones → Tu iPhone), o pegando ese mismo enlace.
struct OnboardingView: View {
    @EnvironmentObject private var session: Session
    @State private var scanning = false
    @State private var pasted = ""
    @State private var error: String?

    var body: some View {
        ScrollView {
            VStack(spacing: 22) {
                HoloCoreView(phase: .idle, showLabel: false)
                    .frame(width: 200, height: 200)
                    .padding(.top, 36)
                Text("J.A.R.V.I.S")
                    .font(Theme.display(30, weight: .heavy))
                    .tracking(8)
                    .foregroundStyle(Theme.ice)
                    .shadow(color: Theme.accent, radius: 10)
                Text("Conecta la app con tu JARVIS. En el panel de tu Mac, abre **Conexiones → Tu iPhone** y escanea el código.")
                    .multilineTextAlignment(.center)
                    .foregroundStyle(Theme.muted)

                Button { scanning = true } label: {
                    Label("Escanear el código", systemImage: "qrcode.viewfinder")
                        .font(.headline)
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)

                VStack(alignment: .leading, spacing: 8) {
                    Text("O pega el enlace del panel")
                        .font(.footnote)
                        .foregroundStyle(Theme.muted)
                    TextField("https://…ts.net/?token=…", text: $pasted)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .keyboardType(.URL)
                        .padding(12)
                        .background(Theme.surface, in: RoundedRectangle(cornerRadius: 10))
                    Button("Conectar") { connect(pasted) }
                        .disabled(pasted.trimmingCharacters(in: .whitespaces).isEmpty)
                }

                if let error {
                    Text(error)
                        .foregroundStyle(Theme.warning)
                        .multilineTextAlignment(.center)
                }
            }
            .padding(24)
        }
        .sheet(isPresented: $scanning) {
            QRScannerSheet { code in
                scanning = false
                connect(code)
            }
        }
    }

    private func connect(_ text: String) {
        if session.pair(with: text) {
            error = nil
        } else {
            error = "Ese código no es el de un panel de JARVIS. Escanea el de Conexiones → Tu iPhone."
        }
    }
}

struct QRScannerSheet: View {
    let onCode: (String) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var cameraAllowed: Bool?

    var body: some View {
        NavigationStack {
            Group {
                switch cameraAllowed {
                case .none:
                    ProgressView()
                case .some(true) where DataScannerViewController.isSupported:
                    QRScanner(onCode: onCode).ignoresSafeArea()
                default:
                    ContentUnavailableView(
                        "No se puede usar la cámara",
                        systemImage: "camera.fill",
                        description: Text("Permite la cámara a JARVIS en Ajustes, o pega el enlace del panel.")
                    )
                }
            }
            .navigationTitle("Código del panel")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cerrar") { dismiss() } }
            }
            .task { cameraAllowed = await AVCaptureDevice.requestAccess(for: .video) }
        }
    }
}

struct QRScanner: UIViewControllerRepresentable {
    let onCode: (String) -> Void

    func makeUIViewController(context: Context) -> DataScannerViewController {
        let scanner = DataScannerViewController(
            recognizedDataTypes: [.barcode(symbologies: [.qr])],
            qualityLevel: .balanced,
            recognizesMultipleItems: false,
            isHighFrameRateTrackingEnabled: false,
            isHighlightingEnabled: true
        )
        scanner.delegate = context.coordinator
        DispatchQueue.main.async { try? scanner.startScanning() }
        return scanner
    }

    func updateUIViewController(_ controller: DataScannerViewController, context: Context) {}

    func makeCoordinator() -> Coordinator { Coordinator(onCode: onCode) }

    final class Coordinator: NSObject, DataScannerViewControllerDelegate {
        private let onCode: (String) -> Void
        private var done = false

        init(onCode: @escaping (String) -> Void) {
            self.onCode = onCode
        }

        func dataScanner(_ dataScanner: DataScannerViewController, didAdd addedItems: [RecognizedItem], allItems: [RecognizedItem]) {
            guard !done else { return }
            for item in addedItems {
                if case .barcode(let barcode) = item, let value = barcode.payloadStringValue {
                    done = true
                    dataScanner.stopScanning()
                    onCode(value)
                    return
                }
            }
        }
    }
}
