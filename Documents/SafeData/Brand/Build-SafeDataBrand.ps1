[CmdletBinding()]
param(
    [string]$OutputFolder = (Join-Path $PSScriptRoot "Assets")
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$variants = @(
    [pscustomobject]@{ Id = 1; Key = "lifecycle"; Title = "Lifecycle"; Accent = "#F28C45"; Kind = "lifecycle" }
    [pscustomobject]@{ Id = 2; Key = "policy"; Title = "Retention Policy"; Accent = "#D9823B"; Kind = "policy" }
    [pscustomobject]@{ Id = 3; Key = "records"; Title = "Records"; Accent = "#267E83"; Kind = "records" }
    [pscustomobject]@{ Id = 4; Key = "consent"; Title = "Consent"; Accent = "#168277"; Kind = "consent" }
    [pscustomobject]@{ Id = 5; Key = "rights"; Title = "Data Rights"; Accent = "#3979A5"; Kind = "rights" }
    [pscustomobject]@{ Id = 6; Key = "audit"; Title = "Audit Evidence"; Accent = "#586D85"; Kind = "audit" }
    [pscustomobject]@{ Id = 7; Key = "integrations"; Title = "Integrations"; Accent = "#9A6AA5"; Kind = "integrations" }
    [pscustomobject]@{ Id = 8; Key = "governance"; Title = "Governance"; Accent = "#BA7654"; Kind = "governance" }
)
$ink = "#142B3B"
$paper = "#FAF8F4"
$sizes = @(1024, 512, 256, 128, 64, 48, 32, 16)

$pngFolder = Join-Path $OutputFolder "PNG"
$svgFolder = Join-Path $OutputFolder "SVG"
$icoFolder = Join-Path $OutputFolder "ICO"
foreach ($folder in @($pngFolder, $svgFolder, $icoFolder)) {
    [System.IO.Directory]::CreateDirectory($folder) | Out-Null
}

function Convert-HexColor([string]$Hex) {
    return [System.Drawing.ColorTranslator]::FromHtml($Hex)
}

function New-RoundedRectanglePath([single]$X, [single]$Y, [single]$Width, [single]$Height, [single]$Radius) {
    $path = New-Object System.Drawing.Drawing2D.GraphicsPath
    $diameter = $Radius * 2
    $path.AddArc($X, $Y, $diameter, $diameter, 180, 90)
    $path.AddArc($X + $Width - $diameter, $Y, $diameter, $diameter, 270, 90)
    $path.AddArc($X + $Width - $diameter, $Y + $Height - $diameter, $diameter, $diameter, 0, 90)
    $path.AddArc($X, $Y + $Height - $diameter, $diameter, $diameter, 90, 90)
    $path.CloseFigure()
    return $path
}

function Draw-CenteredText(
    [System.Drawing.Graphics]$Graphics,
    [string]$Text,
    [string]$Family,
    [single]$FontSize,
    [System.Drawing.FontStyle]$Style,
    [System.Drawing.Color]$Color,
    [single]$Y,
    [single]$Height
) {
    $font = New-Object System.Drawing.Font($Family, $FontSize, $Style, [System.Drawing.GraphicsUnit]::Pixel)
    $brush = New-Object System.Drawing.SolidBrush($Color)
    $format = New-Object System.Drawing.StringFormat
    $format.Alignment = [System.Drawing.StringAlignment]::Center
    $format.LineAlignment = [System.Drawing.StringAlignment]::Center
    $Graphics.DrawString($Text, $font, $brush, [System.Drawing.RectangleF]::new(24, $Y, 464, $Height), $format)
    $format.Dispose()
    $brush.Dispose()
    $font.Dispose()
}

function Draw-VariantSymbol(
    [System.Drawing.Graphics]$Graphics,
    [string]$Kind,
    [System.Drawing.Color]$Accent
) {
    $pen = New-Object System.Drawing.Pen($Accent, 9)
    $pen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
    $pen.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
    $thinPen = New-Object System.Drawing.Pen($Accent, 7)
    $thinPen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
    $thinPen.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
    $fill = New-Object System.Drawing.SolidBrush($Accent)

    switch ($Kind) {
        "lifecycle" {
            $Graphics.DrawArc($pen, 195, 87, 122, 122, -52, 286)
            $Graphics.FillEllipse($fill, 302, 94, 18, 18)
            $Graphics.DrawLine($thinPen, 255, 112, 255, 151)
            $Graphics.DrawLine($thinPen, 255, 151, 280, 166)
        }
        "policy" {
            $Graphics.DrawRectangle($pen, 207, 88, 96, 119)
            $Graphics.DrawLine($thinPen, 225, 122, 279, 122)
            $Graphics.DrawLine($thinPen, 225, 148, 279, 148)
            $Graphics.DrawLine($thinPen, 225, 174, 265, 174)
            $Graphics.FillEllipse($fill, 287, 174, 18, 18)
        }
        "records" {
            foreach ($y in @(99, 142, 185)) {
                $Graphics.DrawRoundedRectangle($pen, 205, $y, 102, 29, 8)
                $Graphics.FillEllipse($fill, 219, ($y + 9), 11, 11)
                $Graphics.DrawLine($thinPen, 243, ($y + 14), 286, ($y + 14))
            }
        }
        "consent" {
            $Graphics.DrawEllipse($pen, 198, 91, 114, 114)
            $Graphics.DrawLines($pen, [System.Drawing.Point[]]@(
                [System.Drawing.Point]::new(222, 149),
                [System.Drawing.Point]::new(245, 172),
                [System.Drawing.Point]::new(290, 123)
            ))
        }
        "rights" {
            $Graphics.DrawRectangle($pen, 210, 91, 92, 111)
            $Graphics.DrawLine($thinPen, 229, 120, 279, 120)
            $Graphics.DrawLine($thinPen, 229, 145, 262, 145)
            $Graphics.DrawArc($pen, 239, 148, 67, 61, 5, 250)
            $Graphics.FillEllipse($fill, 235, 156, 17, 17)
        }
        "audit" {
            foreach ($y in @(111, 148, 185)) {
                $Graphics.DrawLine($pen, 208, $y, 224, ($y + 16))
                $Graphics.DrawLine($pen, 224, ($y + 16), 247, ($y - 10))
                $Graphics.DrawLine($thinPen, 263, ($y + 4), 306, ($y + 4))
            }
        }
        "integrations" {
            $Graphics.DrawLine($pen, 219, 126, 255, 102)
            $Graphics.DrawLine($pen, 255, 102, 291, 126)
            $Graphics.DrawLine($pen, 219, 126, 255, 177)
            $Graphics.DrawLine($pen, 291, 126, 255, 177)
            $Graphics.DrawEllipse($pen, 204, 107, 30, 30)
            $Graphics.DrawEllipse($pen, 240, 85, 30, 30)
            $Graphics.DrawEllipse($pen, 276, 107, 30, 30)
            $Graphics.DrawEllipse($pen, 240, 162, 30, 30)
        }
        "governance" {
            $Graphics.DrawRectangle($pen, 202, 91, 106, 114)
            $Graphics.DrawLine($thinPen, 220, 120, 289, 120)
            $Graphics.DrawLine($thinPen, 220, 145, 289, 145)
            $Graphics.DrawLine($thinPen, 220, 170, 263, 170)
            $Graphics.FillEllipse($fill, 276, 162, 18, 18)
        }
    }
    $fill.Dispose()
    $thinPen.Dispose()
    $pen.Dispose()
}

function New-IconBitmap([object]$Variant, [int]$Size) {
    $bitmap = New-Object System.Drawing.Bitmap($Size, $Size, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
    $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $graphics.Clear([System.Drawing.Color]::Transparent)
    $graphics.ScaleTransform(($Size / 512.0), ($Size / 512.0))

    $tilePath = New-RoundedRectanglePath 10 10 492 492 72
    $tileBrush = New-Object System.Drawing.SolidBrush((Convert-HexColor $paper))
    $tileBorder = New-Object System.Drawing.Pen((Convert-HexColor "#E8E2D9"), 2)
    $graphics.FillPath($tileBrush, $tilePath)
    $graphics.DrawPath($tileBorder, $tilePath)
    $tileBorder.Dispose()
    $tileBrush.Dispose()
    $tilePath.Dispose()

    $ringPen = New-Object System.Drawing.Pen((Convert-HexColor $ink), 7)
    $graphics.DrawEllipse($ringPen, 181, 73, 150, 150)
    $ringPen.Dispose()
    Draw-VariantSymbol $graphics $Variant.Kind (Convert-HexColor $Variant.Accent)
    Draw-CenteredText $graphics "SafeData" "Georgia" 48 ([System.Drawing.FontStyle]::Bold) (Convert-HexColor $ink) 268 62
    Draw-CenteredText $graphics "by 3Consulting" "Segoe UI" 22 ([System.Drawing.FontStyle]::Regular) (Convert-HexColor "#40576A") 329 36
    Draw-CenteredText $graphics $Variant.Title.ToUpperInvariant() "Segoe UI" 15 ([System.Drawing.FontStyle]::Bold) (Convert-HexColor $Variant.Accent) 372 30

    $graphics.Dispose()
    return $bitmap
}

function New-VariantSvg([object]$Variant) {
    $accent = $Variant.Accent
    $inkFill = $ink
    $symbol = switch ($Variant.Kind) {
        "lifecycle" { '<path d="M205 112 A61 61 0 1 1 296 199" fill="none" stroke="' + $accent + '" stroke-width="9" stroke-linecap="round"/><circle cx="302" cy="103" r="9" fill="' + $accent + '"/><path d="M256 126v28l23 14" fill="none" stroke="' + $accent + '" stroke-width="7" stroke-linecap="round"/>' }
        "policy" { '<rect x="207" y="88" width="96" height="119" rx="5" fill="none" stroke="' + $accent + '" stroke-width="8"/><path d="M225 122h54M225 148h54M225 174h40" stroke="' + $accent + '" stroke-width="7" stroke-linecap="round"/><circle cx="296" cy="183" r="9" fill="' + $accent + '"/>' }
        "records" { '<g fill="none" stroke="' + $accent + '" stroke-width="7"><rect x="205" y="99" width="102" height="29" rx="8"/><rect x="205" y="142" width="102" height="29" rx="8"/><rect x="205" y="185" width="102" height="29" rx="8"/></g><g fill="' + $accent + '"><circle cx="225" cy="113" r="5"/><circle cx="225" cy="156" r="5"/><circle cx="225" cy="199" r="5"/></g><path d="M245 113h42M245 156h42M245 199h42" stroke="' + $accent + '" stroke-width="6" stroke-linecap="round"/>' }
        "consent" { '<circle cx="255" cy="148" r="58" fill="none" stroke="' + $accent + '" stroke-width="8"/><path d="m222 149 23 23 45-49" fill="none" stroke="' + $accent + '" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/>' }
        "rights" { '<rect x="210" y="91" width="92" height="111" rx="5" fill="none" stroke="' + $accent + '" stroke-width="8"/><path d="M229 120h50M229 145h33M245 176a31 31 0 1 0 52-21" fill="none" stroke="' + $accent + '" stroke-width="7" stroke-linecap="round"/><circle cx="245" cy="176" r="8" fill="' + $accent + '"/>' }
        "audit" { '<g fill="none" stroke="' + $accent + '" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"><path d="m208 111 16 16 23-26M263 115h43"/><path d="m208 148 16 16 23-26M263 152h43"/><path d="m208 185 16 16 23-26M263 189h43"/></g>' }
        "integrations" { '<g fill="none" stroke="' + $accent + '" stroke-width="8"><path d="m219 122 36-24 36 24-36 51z"/><circle cx="219" cy="122" r="14" fill="' + $paper + '"/><circle cx="255" cy="98" r="14" fill="' + $paper + '"/><circle cx="291" cy="122" r="14" fill="' + $paper + '"/><circle cx="255" cy="173" r="14" fill="' + $paper + '"/></g>' }
        "governance" { '<rect x="202" y="91" width="106" height="114" rx="5" fill="none" stroke="' + $accent + '" stroke-width="8"/><path d="M220 120h69M220 145h69M220 170h43" stroke="' + $accent + '" stroke-width="7" stroke-linecap="round"/><circle cx="284" cy="177" r="9" fill="' + $accent + '"/>' }
    }
    return @"
<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512" role="img" aria-label="SafeData by 3Consulting — $($Variant.Title)">
  <rect x="10" y="10" width="492" height="492" rx="72" fill="$paper" stroke="#E8E2D9" stroke-width="2"/>
  <circle cx="256" cy="148" r="75" fill="none" stroke="$inkFill" stroke-width="7"/>
  $symbol
  <text x="256" y="311" text-anchor="middle" fill="$inkFill" font-family="Georgia,serif" font-size="48" font-weight="bold">SafeData</text>
  <text x="256" y="354" text-anchor="middle" fill="#40576A" font-family="Segoe UI,Arial,sans-serif" font-size="22">by 3Consulting</text>
  <text x="256" y="392" text-anchor="middle" fill="$accent" font-family="Segoe UI,Arial,sans-serif" font-size="15" font-weight="bold" letter-spacing="1.2">$($Variant.Title.ToUpperInvariant())</text>
</svg>
"@
}

function Write-MultiSizeIcon([string]$Path, [string[]]$ImagePaths) {
    $stream = [System.IO.MemoryStream]::new()
    $writer = [System.IO.BinaryWriter]::new($stream)
    $writer.Write([UInt16]0)
    $writer.Write([UInt16]1)
    $writer.Write([UInt16]$ImagePaths.Count)
    $offset = 6 + (16 * $ImagePaths.Count)
    $imageBytes = @()
    foreach ($imagePath in $ImagePaths) {
        $bytes = [System.IO.File]::ReadAllBytes($imagePath)
        $bitmap = [System.Drawing.Bitmap]::FromStream([System.IO.MemoryStream]::new($bytes))
        $width = $bitmap.Width
        $height = $bitmap.Height
        $bitmap.Dispose()
        $entryWidth = if ($width -eq 256) { 0 } else { $width }
        $entryHeight = if ($height -eq 256) { 0 } else { $height }
        $writer.Write([byte]$entryWidth)
        $writer.Write([byte]$entryHeight)
        $writer.Write([byte]0)
        $writer.Write([byte]0)
        $writer.Write([UInt16]1)
        $writer.Write([UInt16]32)
        $writer.Write([UInt32]$bytes.Length)
        $writer.Write([UInt32]$offset)
        $offset += $bytes.Length
        $imageBytes += ,$bytes
    }
    foreach ($bytes in $imageBytes) {
        $writer.Write($bytes)
    }
    $writer.Flush()
    [System.IO.File]::WriteAllBytes($Path, $stream.ToArray())
    $writer.Dispose()
    $stream.Dispose()
}

foreach ($variant in $variants) {
    $baseName = "SafeData-{0:D2}-{1}" -f $variant.Id, $variant.Key
    [System.IO.File]::WriteAllText(
        (Join-Path $svgFolder "$baseName.svg"),
        (New-VariantSvg $variant),
        [System.Text.UTF8Encoding]::new($false)
    )
    foreach ($size in $sizes) {
        $bitmap = New-IconBitmap $variant $size
        $pngPath = Join-Path $pngFolder ("{0}-{1}px.png" -f $baseName, $size)
        $bitmap.Save($pngPath, [System.Drawing.Imaging.ImageFormat]::Png)
        $bitmap.Dispose()
    }
    $icoSizes = @(16, 32, 48, 64, 128, 256)
    $icoImages = @($icoSizes | ForEach-Object {
        Join-Path $pngFolder ("{0}-{1}px.png" -f $baseName, $_)
    })
    Write-MultiSizeIcon (Join-Path $icoFolder "$baseName.ico") $icoImages
}

$contact = New-Object System.Drawing.Bitmap(1600, 1000, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
$contactGraphics = [System.Drawing.Graphics]::FromImage($contact)
$contactGraphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$contactGraphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
$contactGraphics.Clear((Convert-HexColor "#F0EEE9"))
$contactTitle = New-Object System.Drawing.Font("Georgia", 42, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
$titleBrush = New-Object System.Drawing.SolidBrush((Convert-HexColor $ink))
$contactGraphics.DrawString("SafeData by 3Consulting", $contactTitle, $titleBrush, 70, 32)
$contactTitle.Dispose()
$titleBrush.Dispose()
for ($i = 0; $i -lt $variants.Count; $i++) {
    $variant = $variants[$i]
    $bitmap = New-IconBitmap $variant 512
    $column = $i % 4
    $row = [math]::Floor($i / 4)
    $x = 37 + ($column * 390)
    $y = 118 + ($row * 435)
    $contactGraphics.DrawImage($bitmap, $x, $y, 320, 320)
    $labelFont = New-Object System.Drawing.Font("Segoe UI", 22, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
    $labelBrush = New-Object System.Drawing.SolidBrush((Convert-HexColor $ink))
    $contactGraphics.DrawString(("{0:D2}  {1}" -f $variant.Id, $variant.Title), $labelFont, $labelBrush, $x, ($y + 326))
    $labelBrush.Dispose()
    $labelFont.Dispose()
    $bitmap.Dispose()
}
$contactGraphics.Dispose()
$contact.Save((Join-Path $OutputFolder "SafeData-icon-contact-sheet.png"), [System.Drawing.Imaging.ImageFormat]::Png)
$contact.Dispose()

Write-Host "SafeData logo assets created in: $OutputFolder"
Write-Host ("{0} variants; {1} PNG sizes per variant; {2} multi-size Windows icons." -f $variants.Count, $sizes.Count, $variants.Count)
