pluginManagement {
    repositories {
        google {
            mavenContent {
                includeGroupAndSubgroups("androidx")
                includeGroupAndSubgroups("com.android")
                includeGroupAndSubgroups("com.google")
            }
        }
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google {
            mavenContent {
                includeGroupAndSubgroups("androidx")
                includeGroupAndSubgroups("com.android")
                includeGroupAndSubgroups("com.google")
            }
        }
        mavenCentral()
        // Wear Engine SDK (com.huawei.hms:wearengine) and its com.huawei.hmf:tasks dependency.
        maven("https://developer.huawei.com/repo/") {
            content {
                includeGroupAndSubgroups("com.huawei")
            }
        }
    }
}

rootProject.name = "gtpush-phone"
include(":app")
