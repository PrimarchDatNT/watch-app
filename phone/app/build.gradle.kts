plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
}

fun gtpush(name: String): String = providers.gradleProperty("gtpush.$name").getOrElse("")

android {
    namespace = "com.datnt.gtpush"
    compileSdk = 37

    defaultConfig {
        applicationId = "com.datnt.gtpush"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "1.0.0"

        manifestPlaceholders["huaweiAppId"] = gtpush("huaweiAppId")
        buildConfigField("String", "HUAWEI_APP_ID", "\"${gtpush("huaweiAppId")}\"")
        buildConfigField("String", "WATCH_PACKAGE", "\"${gtpush("watchPackage")}\"")
        buildConfigField("String", "WATCH_FINGERPRINT", "\"${gtpush("watchFingerprint")}\"")
        buildConfigField("int", "HTTP_PORT", gtpush("httpPort").ifEmpty { "8765" })
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }
}

dependencies {
    implementation(libs.huawei.wearengine)

    implementation(platform(libs.compose.bom))
    implementation(libs.compose.ui)
    implementation(libs.compose.material3)
    implementation(libs.compose.ui.tooling.preview)
    debugImplementation(libs.compose.ui.tooling)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)
}
