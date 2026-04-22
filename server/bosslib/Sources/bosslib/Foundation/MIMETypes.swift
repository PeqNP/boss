/// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

import Foundation

public enum MIMEType: String {
    case aac
    case apng
    case avig
    case avi
    case bmp
    case css
    case csv
    case doc
    case docx
    case gz
    case gif
    case htm, html
    case jpg, jpeg
    case js
    case json
    case jsonld
    case mid
    case midi
    case mjs
    case mp3
    case mp4
    case mpeg
    case odp
    case odt
    case oga
    case ogv
    case ogx
    case otf
    case pdf
    case png
    case ppt
    case pptx
    case rar
    case rtf
    case svg
    case tar
    case tif, tiff
    case ttf
    case txt
    case wav
    case weba
    case webm
    case webp
    case woff
    case woff2
    case xls
    case xlsx
    case xml
    case zip
}

public func mimeType(for fileURL: URL) -> String {
    let ext = fileURL.pathExtension
    guard let mimeType = MIMEType.init(rawValue: ext.lowercased()) else {
        return "application/octet-stream"
    }
    
    return switch mimeType {
    case .aac: "audio/aac"
    case .apng: "image/apng"
    case .avig: "image/avif"
    case .avi: "video/x-msvideo"
    case .bmp: "image/bmp"
    case .css: "text/css"
    case .csv: "text/csv"
    case .doc: "application/msword"
    case .docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    case .gz: "application/gzip"
    case .gif: "image/gif"
    case .htm, .html: "text/html"
    case .jpg, .jpeg: "image/jpeg"
    case .js: "text/javascript"
    case .json: "application/json"
    case .jsonld: "application/ld+json"
    case .mid, .midi: "audio/midi"
    case .mjs: "text/javascript"
    case .mp3: "audio/mpeg"
    case .mp4: "video/mp4"
    case .mpeg: "video/mpeg"
    case .odp: "application/vnd.oasis.opendocument.spreadsheet"
    case .odt: "application/vnd.oasis.opendocument.text"
    case .oga: "audio/ogg"
    case .ogv: "video/ogg"
    case .ogx: "application/ogg"
    case .otf: "font/otf"
    case .pdf: "application/pdf"
    case .png: "image/png"
    case .ppt: "application/vnd.ms-powerpoint"
    case .pptx: "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    case .rar: "application/vnd.rar"
    case .rtf: "application/rtf"
    case .svg: "image/svg+xml"
    case .tar: "application/x-tar"
    case .tif, .tiff: "image/tiff"
    case .ttf: "font/ttf"
    case .txt: "text/plain"
    case .wav: "audio/wav"
    case .weba: "audio/webm"
    case .webm: "video/webm"
    case .webp: "image/webp"
    case .woff: "font/woff"
    case .woff2: "font/woff2"
    case .xls: "application/vnd.ms-excel"
    case .xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    case .xml: "application/xml"
    case .zip: "application/zip"
    }
}
