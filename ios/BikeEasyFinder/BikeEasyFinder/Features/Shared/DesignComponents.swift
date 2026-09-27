import SwiftUI

enum AppTheme {
    static let brand = Color(red: 0.05, green: 0.34, blue: 0.32)
    static let brandSoft = Color(red: 0.86, green: 0.94, blue: 0.91)
    static let cardBackground = Color(uiColor: .secondarySystemBackground)
}

struct ChoiceChip: View {
    let title: String
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 6) {
                if isSelected {
                    Image(systemName: "checkmark")
                        .font(.caption.bold())
                }
                Text(title)
                    .lineLimit(1)
            }
            .font(.subheadline.weight(.semibold))
            .foregroundStyle(isSelected ? Color.white : Color.primary)
            .frame(maxWidth: .infinity, minHeight: 44)
            .padding(.horizontal, 10)
            .background(isSelected ? AppTheme.brand : AppTheme.cardBackground)
            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
            .overlay {
                if !isSelected {
                    RoundedRectangle(cornerRadius: 12, style: .continuous)
                        .stroke(Color.secondary.opacity(0.25))
                }
            }
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(isSelected ? .isSelected : [])
        .accessibilityValue(isSelected ? "選択中" : "未選択")
    }
}

struct PrimaryBottomAction: View {
    let title: String
    var systemImage: String? = nil
    var isLoading = false
    var isDisabled = false
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 8) {
                if isLoading {
                    ProgressView()
                        .tint(.white)
                } else if let systemImage {
                    Image(systemName: systemImage)
                }
                Text(title)
                    .fontWeight(.bold)
            }
            .frame(maxWidth: .infinity, minHeight: 50)
        }
        .buttonStyle(.borderedProminent)
        .tint(AppTheme.brand)
        .disabled(isDisabled || isLoading)
        .padding(.horizontal)
        .padding(.top, 8)
        .padding(.bottom, 4)
        .background(.bar)
    }
}

struct SpotHero: View {
    let spot: TouringSpot

    var body: some View {
        ZStack(alignment: .bottomLeading) {
            LinearGradient(
                colors: [AppTheme.brand.opacity(0.95), Color.blue.opacity(0.55)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )

            Image(systemName: "mountain.2.fill")
                .font(.system(size: 100))
                .foregroundStyle(.white.opacity(0.16))
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .center)
                .accessibilityHidden(true)

            VStack(alignment: .leading, spacing: 8) {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack {
                        ForEach(spot.tags.sorted(by: { $0.displayName < $1.displayName })) { tag in
                            Text(tag.displayName)
                                .font(.caption.weight(.semibold))
                                .padding(.horizontal, 10)
                                .padding(.vertical, 5)
                                .background(.ultraThinMaterial, in: Capsule())
                        }
                    }
                }
                Text(spot.name)
                    .font(.title.bold())
                    .foregroundStyle(.white)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .padding(20)
        }
        .frame(minHeight: 220)
        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(spot.name)。\(spot.tags.map(\.displayName).sorted().joined(separator: "、"))")
    }
}

struct TimeSummary: View {
    let spot: TouringSpot
    var now = Date()

    private var returnTime: Date {
        Calendar.current.date(byAdding: .minute, value: spot.estimatedTotalMinutes, to: now) ?? now
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("往復・滞在・15分の余裕込み")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Text(spot.formattedEstimatedDuration)
                        .font(.title2.bold())
                }
                Spacer()
                VStack(alignment: .trailing, spacing: 2) {
                    Text("帰着予想")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Text(returnTime, style: .time)
                        .font(.headline)
                }
            }

            ViewThatFits {
                HStack { breakdown }
                VStack(alignment: .leading) { breakdown }
            }
            .font(.subheadline)
            .foregroundStyle(.secondary)
        }
        .padding()
        .background(AppTheme.cardBackground, in: RoundedRectangle(cornerRadius: 14))
        .accessibilityElement(children: .combine)
    }

    @ViewBuilder
    private var breakdown: some View {
        Label("往路 \(spot.outboundMinutes)分", systemImage: "arrow.right")
        Spacer(minLength: 8)
        Label("滞在 \(spot.stayMinutes)分", systemImage: "cup.and.saucer")
        Spacer(minLength: 8)
        Label("復路 \(spot.returnMinutes)分", systemImage: "arrow.left")
    }
}

struct ReasonBlock: View {
    let reason: String

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: "sparkles")
                .foregroundStyle(AppTheme.brand)
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 4) {
                Text("この場所を選んだ理由")
                    .font(.headline)
                Text(reason)
                    .foregroundStyle(.secondary)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(AppTheme.brandSoft.opacity(0.65), in: RoundedRectangle(cornerRadius: 14))
        .accessibilityElement(children: .combine)
    }
}

struct StatusNotice: View {
    enum Kind {
        case info, warning, error

        var icon: String {
            switch self {
            case .info: "info.circle.fill"
            case .warning: "exclamationmark.triangle.fill"
            case .error: "xmark.octagon.fill"
            }
        }

        var color: Color {
            switch self {
            case .info: .blue
            case .warning: .orange
            case .error: .red
            }
        }
    }

    let kind: Kind
    let title: String
    let message: String

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: kind.icon)
                .foregroundStyle(kind.color)
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 3) {
                Text(title).font(.headline)
                Text(message).font(.subheadline).foregroundStyle(.secondary)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(kind.color.opacity(0.09), in: RoundedRectangle(cornerRadius: 12))
        .accessibilityElement(children: .combine)
    }
}

struct UndoBanner: View {
    let message: String
    let undo: () -> Void

    var body: some View {
        HStack(spacing: 12) {
            Text(message)
                .font(.subheadline)
            Spacer()
            Button("取り消す", action: undo)
                .fontWeight(.bold)
        }
        .padding()
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 14))
        .shadow(radius: 8, y: 3)
        .padding(.horizontal)
        .accessibilityElement(children: .contain)
    }
}
