/// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

import bosslib
import Vapor

enum LeanFragment {
    struct Company: Content {
        let id: bosslib.Company.ID
        let name: String
    }

    struct Companies: Content {
        let companies: [LeanFragment.Company]
    }
}

extension bosslib.Company {
    func makeCompanyOption() -> LeanFragment.Company {
        .init(id: id, name: name)
    }
}
