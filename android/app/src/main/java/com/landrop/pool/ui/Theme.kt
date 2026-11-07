package com.landrop.pool.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

val PureBlack = Color(0xFF000000)
val DarkCard = Color(0xFF09090B)
val DarkCardItem = Color(0xFF121214)
val DarkBorder = Color(0xFF27272A)
val TextWhite = Color(0xFFFFFFFF)
val TextMuted = Color(0xFFA1A1AA)
val AccentGreen = Color(0xFF10B981)
val AccentRed = Color(0xFFEF4444)

private val DarkColorScheme = darkColorScheme(
    primary = Color.White,
    secondary = AccentGreen,
    background = PureBlack,
    surface = DarkCard,
    surfaceVariant = DarkCardItem,
    onPrimary = Color.Black,
    onSecondary = Color.Black,
    onBackground = TextWhite,
    onSurface = TextWhite,
    outline = DarkBorder
)

@Composable
fun LanDropTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = DarkColorScheme,
        content = content
    )
}
