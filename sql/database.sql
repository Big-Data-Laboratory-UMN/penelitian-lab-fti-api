CREATE DATABASE `fti_lab_booking` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci */ /*!80016 DEFAULT ENCRYPTION='N' */;

-- fti_lab_booking.tblh_activity_logs definition

CREATE TABLE `tblh_activity_logs` (
  `nid` int NOT NULL AUTO_INCREMENT,
  `nid_user` int NOT NULL,
  `vaction` varchar(50) NOT NULL,
  `vtarget_model` varchar(100) NOT NULL,
  `vtarget_identifier` varchar(255) NOT NULL,
  `jbefore` json DEFAULT NULL,
  `jafter` json DEFAULT NULL,
  `dtimestamp` datetime DEFAULT NULL,
  `vip_address` varchar(100) DEFAULT NULL,
  `vuser_agent` text,
  PRIMARY KEY (`nid`),
  KEY `ix_tblh_activity_logs_dtimestamp` (`dtimestamp`),
  KEY `ix_tblh_activity_logs_nid_user` (`nid_user`),
  KEY `ix_tblh_activity_logs_vaction` (`vaction`),
  KEY `ix_tblh_activity_logs_vtarget_identifier` (`vtarget_identifier`),
  KEY `ix_tblh_activity_logs_vtarget_model` (`vtarget_model`),
  CONSTRAINT `tblh_activity_logs_ibfk_1` FOREIGN KEY (`nid_user`) REFERENCES `tbls_users` (`nid`)
) ENGINE=InnoDB AUTO_INCREMENT=334 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- fti_lab_booking.tblh_security_logs definition

CREATE TABLE `tblh_security_logs` (
  `nid` int NOT NULL AUTO_INCREMENT,
  `nid_user` int DEFAULT NULL,
  `vaction` varchar(100) NOT NULL,
  `vip_address` varchar(100) DEFAULT NULL,
  `vuser_agent` text,
  `vdetails` text,
  `dtimestamp` datetime DEFAULT NULL,
  PRIMARY KEY (`nid`),
  KEY `ix_tblh_security_logs_dtimestamp` (`dtimestamp`),
  KEY `ix_tblh_security_logs_nid_user` (`nid_user`),
  KEY `ix_tblh_security_logs_vaction` (`vaction`),
  CONSTRAINT `tblh_security_logs_ibfk_1` FOREIGN KEY (`nid_user`) REFERENCES `tbls_users` (`nid`)
) ENGINE=InnoDB AUTO_INCREMENT=644 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- fti_lab_booking.tblm_files definition

CREATE TABLE `tblm_files` (
  `nid` int NOT NULL AUTO_INCREMENT,
  `vcode` varchar(100) DEFAULT NULL,
  `vname` varchar(255) NOT NULL,
  `vtype` text NOT NULL,
  `vpath` text NOT NULL,
  `vextension` varchar(100) NOT NULL,
  `nsize` float NOT NULL,
  `vcategory` varchar(100) NOT NULL,
  `nis_public` int NOT NULL,
  `nstatus` int NOT NULL,
  `dcreated_at` datetime DEFAULT NULL,
  `vcreated_by` varchar(100) DEFAULT NULL,
  `dmodified_at` datetime DEFAULT NULL,
  `vmodified_by` varchar(100) DEFAULT NULL,
  `dsort_at` datetime DEFAULT NULL,
  PRIMARY KEY (`nid`),
  UNIQUE KEY `uq_files_vcode_vname` (`vcode`,`vname`),
  UNIQUE KEY `ix_tblm_files_vcode` (`vcode`),
  CONSTRAINT `chk_files_nis_public_values` CHECK ((`nis_public` in (0,1))),
  CONSTRAINT `chk_files_nstatus_values` CHECK ((`nstatus` in (0,1)))
) ENGINE=InnoDB AUTO_INCREMENT=251 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- fti_lab_booking.tblm_building definition

CREATE TABLE `tblm_building` (
  `nid` int NOT NULL AUTO_INCREMENT,
  `vcode` varchar(100) DEFAULT NULL,
  `vname` varchar(255) NOT NULL,
  `vdesc` text NOT NULL,
  `nstatus` int NOT NULL,
  `dcreated_at` datetime DEFAULT NULL,
  `vcreated_by` varchar(100) DEFAULT NULL,
  `dmodified_at` datetime DEFAULT NULL,
  `vmodified_by` varchar(100) DEFAULT NULL,
  `dsort_at` datetime DEFAULT NULL,
  PRIMARY KEY (`nid`),
  UNIQUE KEY `uq_building_vcode_vname` (`vcode`,`vname`),
  UNIQUE KEY `ix_tblm_building_vcode` (`vcode`),
  CONSTRAINT `chk_building_nstatus_values` CHECK ((`nstatus` in (0,1)))
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- fti_lab_booking.tblm_department definition

CREATE TABLE `tblm_department` (
  `nid` int NOT NULL AUTO_INCREMENT,
  `vcode` varchar(100) DEFAULT NULL,
  `vname` varchar(255) NOT NULL,
  `vdesc` text NOT NULL,
  `nstatus` int NOT NULL,
  `dcreated_at` datetime DEFAULT NULL,
  `vcreated_by` varchar(100) DEFAULT NULL,
  `dmodified_at` datetime DEFAULT NULL,
  `vmodified_by` varchar(100) DEFAULT NULL,
  `dsort_at` datetime DEFAULT NULL,
  PRIMARY KEY (`nid`),
  UNIQUE KEY `uq_departmment_vcode_vname` (`vcode`,`vname`),
  UNIQUE KEY `ix_tblm_department_vcode` (`vcode`),
  CONSTRAINT `chk_department_nstatus_values` CHECK ((`nstatus` in (0,1)))
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- fti_lab_booking.tblm_facility definition

CREATE TABLE `tblm_facility` (
  `nid` int NOT NULL AUTO_INCREMENT,
  `vcode` varchar(100) DEFAULT NULL,
  `vname` varchar(255) NOT NULL,
  `vdesc` text NOT NULL,
  `nstatus` int NOT NULL,
  `nid_file` int NOT NULL,
  `dcreated_at` datetime DEFAULT NULL,
  `vcreated_by` varchar(100) DEFAULT NULL,
  `dmodified_at` datetime DEFAULT NULL,
  `vmodified_by` varchar(100) DEFAULT NULL,
  `dsort_at` datetime DEFAULT NULL,
  PRIMARY KEY (`nid`),
  UNIQUE KEY `uq_facilities_vcode_vname` (`vcode`,`vname`),
  UNIQUE KEY `ix_tblm_facility_vcode` (`vcode`),
  KEY `nid_file` (`nid_file`),
  CONSTRAINT `tblm_facility_ibfk_1` FOREIGN KEY (`nid_file`) REFERENCES `tblm_files` (`nid`),
  CONSTRAINT `chk_facilities_nstatus_values` CHECK ((`nstatus` in (0,1)))
) ENGINE=InnoDB AUTO_INCREMENT=14 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- fti_lab_booking.tblm_knowledge_base definition

CREATE TABLE `tblm_knowledge_base` (
  `nid` int NOT NULL AUTO_INCREMENT,
  `vcategory` varchar(255) DEFAULT NULL,
  `vcontext` text,
  `vanswer` text,
  `nstatus` int NOT NULL,
  `dcreated_at` datetime DEFAULT NULL,
  `vcreated_by` varchar(100) DEFAULT NULL,
  `dmodified_at` datetime DEFAULT NULL,
  `vmodified_by` varchar(100) DEFAULT NULL,
  `dsort_at` datetime DEFAULT NULL,
  PRIMARY KEY (`nid`)
) ENGINE=InnoDB AUTO_INCREMENT=52 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- fti_lab_booking.tblm_lab definition

CREATE TABLE `tblm_lab` (
  `nid` int NOT NULL AUTO_INCREMENT,
  `vcode` varchar(100) DEFAULT NULL,
  `vname` varchar(255) NOT NULL,
  `vdesc` text NOT NULL,
  `ncapacity` int NOT NULL,
  `nid_building` int NOT NULL,
  `vroom_number` varchar(100) NOT NULL,
  `nstatus` int NOT NULL,
  `dcreated_at` datetime DEFAULT NULL,
  `vcreated_by` varchar(100) DEFAULT NULL,
  `dmodified_at` datetime DEFAULT NULL,
  `vmodified_by` varchar(100) DEFAULT NULL,
  `dsort_at` datetime DEFAULT NULL,
  PRIMARY KEY (`nid`),
  UNIQUE KEY `uq_lab_vcode_vname` (`vcode`,`vname`),
  UNIQUE KEY `ix_tblm_lab_vcode` (`vcode`),
  KEY `nid_building` (`nid_building`),
  CONSTRAINT `tblm_lab_ibfk_1` FOREIGN KEY (`nid_building`) REFERENCES `tblm_building` (`nid`),
  CONSTRAINT `chk_lab_nstatus_values` CHECK ((`nstatus` in (0,1)))
) ENGINE=InnoDB AUTO_INCREMENT=24 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- fti_lab_booking.tblm_landing_page_content definition

CREATE TABLE `tblm_landing_page_content` (
  `nid` int NOT NULL AUTO_INCREMENT,
  `vcode` varchar(100) DEFAULT NULL,
  `vabout_header` varchar(255) DEFAULT NULL,
  `vabout_subtext` text,
  `dcreated_at` datetime DEFAULT NULL,
  `vcreated_by` varchar(100) DEFAULT NULL,
  `dmodified_at` datetime DEFAULT NULL,
  `vmodified_by` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`nid`),
  UNIQUE KEY `ix_tblm_landing_page_content_vcode` (`vcode`),
  KEY `ix_tblm_landing_page_content_nid` (`nid`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- fti_lab_booking.tblm_landing_page_slide definition

CREATE TABLE `tblm_landing_page_slide` (
  `nid` int NOT NULL AUTO_INCREMENT,
  `vcode` varchar(100) DEFAULT NULL,
  `nid_landing_page` int NOT NULL,
  `norder` int NOT NULL COMMENT 'Slide order: 1, 2, or 3',
  `vheader` varchar(255) DEFAULT NULL,
  `vsubtext` text,
  `nid_file` int DEFAULT NULL,
  `nstatus` int DEFAULT NULL COMMENT '0:Inactive, 1:Active',
  `dcreated_at` datetime DEFAULT NULL,
  `vcreated_by` varchar(100) DEFAULT NULL,
  `dmodified_at` datetime DEFAULT NULL,
  `vmodified_by` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`nid`),
  UNIQUE KEY `ix_tblm_landing_page_slide_vcode` (`vcode`),
  KEY `nid_landing_page` (`nid_landing_page`),
  KEY `nid_file` (`nid_file`),
  KEY `ix_tblm_landing_page_slide_nid` (`nid`),
  CONSTRAINT `tblm_landing_page_slide_ibfk_1` FOREIGN KEY (`nid_landing_page`) REFERENCES `tblm_landing_page_content` (`nid`),
  CONSTRAINT `tblm_landing_page_slide_ibfk_2` FOREIGN KEY (`nid_file`) REFERENCES `tblm_files` (`nid`),
  CONSTRAINT `slide_norder_check` CHECK ((`norder` in (1,2,3))),
  CONSTRAINT `slide_nstatus_check` CHECK ((`nstatus` in (0,1)))
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- fti_lab_booking.tblm_roles definition

CREATE TABLE `tblm_roles` (
  `nid` int NOT NULL AUTO_INCREMENT,
  `vcode` varchar(100) DEFAULT NULL,
  `vname` varchar(255) NOT NULL,
  `vdesc` text NOT NULL,
  `nstatus` int NOT NULL,
  `dcreated_at` datetime DEFAULT NULL,
  `vcreated_by` varchar(100) DEFAULT NULL,
  `dmodified_at` datetime DEFAULT NULL,
  `vmodified_by` varchar(100) DEFAULT NULL,
  `dsort_at` datetime DEFAULT NULL,
  PRIMARY KEY (`nid`),
  UNIQUE KEY `uq_roles_vcode_vname` (`vcode`,`vname`),
  UNIQUE KEY `ix_tblm_roles_vcode` (`vcode`),
  CONSTRAINT `chk_roles_nstatus_values` CHECK ((`nstatus` in (0,1)))
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- fti_lab_booking.tbls_users definition

CREATE TABLE `tbls_users` (
  `nid` int NOT NULL AUTO_INCREMENT,
  `vcode` varchar(100) DEFAULT NULL,
  `vname` varchar(255) NOT NULL,
  `vphone` varchar(20) DEFAULT NULL,
  `vemail` varchar(255) NOT NULL,
  `vaddress` text,
  `vpassword` varchar(255) DEFAULT NULL,
  `nstatus` int NOT NULL COMMENT 'Status User: 0=Inactive, 1=Active, 2=Pending, 3=Expired',
  `dcreated_at` datetime DEFAULT NULL,
  `vcreated_by` varchar(100) DEFAULT NULL,
  `dmodified_at` datetime DEFAULT NULL,
  `vmodified_by` varchar(100) DEFAULT NULL,
  `dsort_at` datetime DEFAULT NULL,
  PRIMARY KEY (`nid`),
  UNIQUE KEY `ix_tbls_users_vemail` (`vemail`),
  UNIQUE KEY `ix_tbls_users_vcode` (`vcode`),
  CONSTRAINT `chk_users_nstatus_values` CHECK ((`nstatus` in (0,1,2,3)))
) ENGINE=InnoDB AUTO_INCREMENT=23 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- fti_lab_booking.tblt_lab_article definition

CREATE TABLE `tblt_lab_article` (
  `nid` int NOT NULL AUTO_INCREMENT,
  `vcode` varchar(100) DEFAULT NULL,
  `nid_lab` int NOT NULL,
  `nid_user` int NOT NULL,
  `vtitle` varchar(255) NOT NULL,
  `vexcerpt` text,
  `vcontent` text NOT NULL,
  `nis_featured` int DEFAULT NULL COMMENT '0:No, 1:Yes',
  `nstatus` int DEFAULT NULL COMMENT '0:Inactive, 1:Published, 2:Scheduled',
  `dpublished_at` datetime DEFAULT NULL,
  `dcreated_at` datetime DEFAULT NULL,
  `vcreated_by` varchar(100) DEFAULT NULL,
  `dmodified_at` datetime DEFAULT NULL,
  `vmodified_by` varchar(100) DEFAULT NULL,
  `dsort_at` datetime DEFAULT NULL,
  `nid_file` int DEFAULT NULL,
  PRIMARY KEY (`nid`),
  UNIQUE KEY `ix_tblt_lab_article_vcode` (`vcode`),
  KEY `nid_lab` (`nid_lab`),
  KEY `nid_user` (`nid_user`),
  KEY `ix_tblt_lab_article_nid` (`nid`),
  KEY `nid_file` (`nid_file`),
  CONSTRAINT `tblt_lab_article_ibfk_1` FOREIGN KEY (`nid_lab`) REFERENCES `tblm_lab` (`nid`),
  CONSTRAINT `tblt_lab_article_ibfk_2` FOREIGN KEY (`nid_user`) REFERENCES `tbls_users` (`nid`),
  CONSTRAINT `tblt_lab_article_ibfk_3` FOREIGN KEY (`nid_file`) REFERENCES `tblm_files` (`nid`),
  CONSTRAINT `article_nis_featured_check` CHECK ((`nis_featured` in (0,1))),
  CONSTRAINT `article_nstatus_check` CHECK ((`nstatus` in (0,1,2)))
) ENGINE=InnoDB AUTO_INCREMENT=17 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- fti_lab_booking.tblr_article_tag definition

CREATE TABLE `tblr_article_tag` (
  `nid` int NOT NULL AUTO_INCREMENT,
  `nid_article` int NOT NULL,
  `vtag` varchar(100) NOT NULL,
  PRIMARY KEY (`nid`),
  KEY `nid_article` (`nid_article`),
  KEY `ix_tblr_article_tag_nid` (`nid`),
  CONSTRAINT `tblr_article_tag_ibfk_1` FOREIGN KEY (`nid_article`) REFERENCES `tblt_lab_article` (`nid`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=68 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- fti_lab_booking.tblr_lab_facility definition

CREATE TABLE `tblr_lab_facility` (
  `nid` int NOT NULL AUTO_INCREMENT,
  `vcode` varchar(100) NOT NULL,
  `vcode_lab` varchar(100) NOT NULL,
  `vcode_facility` varchar(100) NOT NULL,
  `nid_lab` int NOT NULL,
  `nid_facility` int NOT NULL,
  `nstatus` int NOT NULL,
  `dcreated_at` datetime DEFAULT NULL,
  `vcreated_by` varchar(100) DEFAULT NULL,
  `dmodified_at` datetime DEFAULT NULL,
  `vmodified_by` varchar(100) DEFAULT NULL,
  `dsort_at` datetime DEFAULT NULL,
  PRIMARY KEY (`nid`),
  UNIQUE KEY `u_facility_lab_combination` (`nid_lab`,`nid_facility`),
  UNIQUE KEY `ix_tblr_lab_facility_vcode` (`vcode`),
  KEY `nid_facility` (`nid_facility`),
  CONSTRAINT `tblr_lab_facility_ibfk_1` FOREIGN KEY (`nid_facility`) REFERENCES `tblm_facility` (`nid`),
  CONSTRAINT `tblr_lab_facility_ibfk_2` FOREIGN KEY (`nid_lab`) REFERENCES `tblm_lab` (`nid`),
  CONSTRAINT `chk_facility_lab_nstatus_values` CHECK ((`nstatus` in (0,1)))
) ENGINE=InnoDB AUTO_INCREMENT=16 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- fti_lab_booking.tblr_lab_gallery definition

CREATE TABLE `tblr_lab_gallery` (
  `nid` int NOT NULL AUTO_INCREMENT,
  `vcode` varchar(100) DEFAULT NULL,
  `nid_lab` int NOT NULL,
  `nid_file` int NOT NULL,
  `ntype` int NOT NULL COMMENT '1 = Hero Image, 2 = Gallery Image',
  `nstatus` int NOT NULL,
  `dcreated_at` datetime DEFAULT NULL,
  `vcreated_by` varchar(100) DEFAULT NULL,
  `dmodified_at` datetime DEFAULT NULL,
  `vmodified_by` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`nid`),
  UNIQUE KEY `uq_lab_gallery_lab_file` (`nid_lab`,`nid_file`),
  UNIQUE KEY `ix_tblr_lab_gallery_vcode` (`vcode`),
  KEY `nid_file` (`nid_file`),
  CONSTRAINT `tblr_lab_gallery_ibfk_1` FOREIGN KEY (`nid_file`) REFERENCES `tblm_files` (`nid`),
  CONSTRAINT `tblr_lab_gallery_ibfk_2` FOREIGN KEY (`nid_lab`) REFERENCES `tblm_lab` (`nid`),
  CONSTRAINT `chk_lab_gallery_nstatus_values` CHECK ((`nstatus` in (0,1))),
  CONSTRAINT `chk_lab_gallery_ntype_values` CHECK ((`ntype` in (1,2)))
) ENGINE=InnoDB AUTO_INCREMENT=81 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- fti_lab_booking.tblt_booking definition

CREATE TABLE `tblt_booking` (
  `nid` int NOT NULL AUTO_INCREMENT,
  `vcode` varchar(100) DEFAULT NULL,
  `nid_lab_facility` int NOT NULL,
  `nid_user` int NOT NULL,
  `dstart` datetime NOT NULL,
  `dend` datetime NOT NULL,
  `vactivity` text,
  `nstatus` int DEFAULT NULL COMMENT '0:Rejected, 1:Approved, 2:Pending, 3:Canceled, 4:WaitingForDoc, 5:Done',
  `nbooking_type` int DEFAULT NULL COMMENT '0:Regular, 1:Maintenance',
  `dreviewed_at` datetime DEFAULT NULL,
  `vreviewed_by` varchar(100) DEFAULT NULL,
  `dcreated_at` datetime DEFAULT NULL,
  `vcreated_by` varchar(100) DEFAULT NULL,
  `dmodified_at` datetime DEFAULT NULL,
  `vmodified_by` varchar(100) DEFAULT NULL,
  `dcanceled_at` datetime DEFAULT NULL,
  `dsort_at` datetime DEFAULT NULL,
  PRIMARY KEY (`nid`),
  UNIQUE KEY `ix_tblt_booking_vcode` (`vcode`),
  KEY `nid_lab_facility` (`nid_lab_facility`),
  KEY `nid_user` (`nid_user`),
  KEY `ix_tblt_booking_nid` (`nid`),
  CONSTRAINT `tblt_booking_ibfk_1` FOREIGN KEY (`nid_lab_facility`) REFERENCES `tblr_lab_facility` (`nid`),
  CONSTRAINT `tblt_booking_ibfk_2` FOREIGN KEY (`nid_user`) REFERENCES `tbls_users` (`nid`),
  CONSTRAINT `booking_nbooking_type_check` CHECK ((`nbooking_type` in (0,1))),
  CONSTRAINT `booking_nstatus_check` CHECK ((`nstatus` in (0,1,2,3,4,5)))
) ENGINE=InnoDB AUTO_INCREMENT=93 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- fti_lab_booking.tbls_token definition

CREATE TABLE `tbls_token` (
  `nid` int NOT NULL AUTO_INCREMENT,
  `nid_user` int NOT NULL COMMENT 'Foreign key ke tabel user (tbls_users)',
  `ntoken_type` int NOT NULL COMMENT 'Tipe token: 1=Aktivasi, 2=Sesi Login, 3=Reset Password, 4=Ganti Email',
  `vcode` varchar(255) NOT NULL COMMENT 'Kode unik untuk token aktivasi atau password reset',
  `vnew_email` varchar(255) DEFAULT NULL COMMENT 'Email baru yang menunggu verifikasi',
  `vaccess_token` text COMMENT 'JWT access token untuk sesi login',
  `vrefresh_token` text COMMENT 'JWT refresh token untuk memperbarui access token',
  `vbrowser_info` text COMMENT 'Informasi browser/User-Agent dari user',
  `vip_address` varchar(50) DEFAULT NULL COMMENT 'Alamat IP user saat request token',
  `dexpires_at` datetime NOT NULL COMMENT 'Waktu kedaluwarsa untuk token aktivasi atau access token',
  `drefresh_expire_at` datetime DEFAULT NULL COMMENT 'Waktu kedaluwarsa untuk refresh token',
  `nstatus` int NOT NULL COMMENT 'Status token: 1=Aktif, 0=Tidak Aktif/Sudah digunakan',
  `dcreated_at` datetime NOT NULL,
  `dmodified_at` datetime DEFAULT NULL,
  PRIMARY KEY (`nid`),
  UNIQUE KEY `ix_tbls_token_vcode` (`vcode`),
  KEY `nid_user` (`nid_user`),
  KEY `ix_tbls_token_ntoken_type` (`ntoken_type`),
  CONSTRAINT `tbls_token_ibfk_1` FOREIGN KEY (`nid_user`) REFERENCES `tbls_users` (`nid`),
  CONSTRAINT `chk_token_nstatus_values` CHECK ((`nstatus` in (0,1))),
  CONSTRAINT `chk_token_type_values` CHECK ((`ntoken_type` in (1,2,3,4)))
) ENGINE=InnoDB AUTO_INCREMENT=14 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- fti_lab_booking.tblr_user_access definition

CREATE TABLE `tblr_user_access` (
  `nid` int NOT NULL AUTO_INCREMENT,
  `vcode` varchar(100) NOT NULL,
  `nid_user` int NOT NULL,
  `nid_role` int NOT NULL,
  `nid_department` int DEFAULT NULL,
  `nid_lab` int DEFAULT NULL,
  `nstatus` int NOT NULL,
  `dcreated_at` datetime DEFAULT NULL,
  `vcreated_by` varchar(100) DEFAULT NULL,
  `dmodified_at` datetime DEFAULT NULL,
  `vmodified_by` varchar(100) DEFAULT NULL,
  `dsort_at` datetime DEFAULT NULL,
  PRIMARY KEY (`nid`),
  UNIQUE KEY `ix_tblr_user_access_vcode` (`vcode`),
  UNIQUE KEY `uq_user_access_combination` (`nid_user`,`nid_role`,`nid_department`,`nid_lab`),
  KEY `nid_department` (`nid_department`),
  KEY `nid_lab` (`nid_lab`),
  KEY `nid_role` (`nid_role`),
  CONSTRAINT `tblr_user_access_ibfk_1` FOREIGN KEY (`nid_department`) REFERENCES `tblm_department` (`nid`),
  CONSTRAINT `tblr_user_access_ibfk_2` FOREIGN KEY (`nid_lab`) REFERENCES `tblm_lab` (`nid`),
  CONSTRAINT `tblr_user_access_ibfk_3` FOREIGN KEY (`nid_role`) REFERENCES `tblm_roles` (`nid`),
  CONSTRAINT `tblr_user_access_ibfk_4` FOREIGN KEY (`nid_user`) REFERENCES `tbls_users` (`nid`),
  CONSTRAINT `chk_user_access_nstatus_values` CHECK ((`nstatus` in (0,1)))
) ENGINE=InnoDB AUTO_INCREMENT=72 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- fti_lab_booking.tblr_department_lab definition

CREATE TABLE `tblr_department_lab` (
  `nid` int NOT NULL AUTO_INCREMENT,
  `vcode` varchar(100) NOT NULL,
  `nid_lab` int NOT NULL,
  `nid_department` int NOT NULL,
  `nstatus` int NOT NULL,
  `dcreated_at` datetime DEFAULT NULL,
  `vcreated_by` varchar(100) DEFAULT NULL,
  `dmodified_at` datetime DEFAULT NULL,
  `vmodified_by` varchar(100) DEFAULT NULL,
  `dsort_at` datetime DEFAULT NULL,
  PRIMARY KEY (`nid`),
  UNIQUE KEY `u_department_lab_combination` (`nid_lab`,`nid_department`),
  UNIQUE KEY `ix_tblr_department_lab_vcode` (`vcode`),
  KEY `nid_department` (`nid_department`),
  CONSTRAINT `tblr_department_lab_ibfk_1` FOREIGN KEY (`nid_department`) REFERENCES `tblm_department` (`nid`),
  CONSTRAINT `tblr_department_lab_ibfk_2` FOREIGN KEY (`nid_lab`) REFERENCES `tblm_lab` (`nid`),
  CONSTRAINT `chk_department_lab_nstatus_values` CHECK ((`nstatus` in (0,1)))
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- fti_lab_booking.tblr_booking_files definition

CREATE TABLE `tblr_booking_files` (
  `nid` int NOT NULL AUTO_INCREMENT,
  `vcode` varchar(100) NOT NULL,
  `nid_booking` int NOT NULL,
  `nid_file` int NOT NULL,
  `vtype` varchar(50) NOT NULL,
  `nstatus` int NOT NULL,
  `dcreated_at` datetime DEFAULT NULL,
  `vcreated_by` varchar(100) DEFAULT NULL,
  `dmodified_at` datetime DEFAULT NULL,
  `vmodified_by` varchar(100) DEFAULT NULL,
  `dsort_at` datetime DEFAULT NULL,
  PRIMARY KEY (`nid`),
  UNIQUE KEY `ix_tblr_booking_files_vcode` (`vcode`),
  KEY `nid_booking` (`nid_booking`),
  KEY `nid_file` (`nid_file`),
  KEY `ix_tblr_booking_files_vtype` (`vtype`),
  CONSTRAINT `tblr_booking_files_ibfk_1` FOREIGN KEY (`nid_booking`) REFERENCES `tblt_booking` (`nid`),
  CONSTRAINT `tblr_booking_files_ibfk_2` FOREIGN KEY (`nid_file`) REFERENCES `tblm_files` (`nid`)
) ENGINE=InnoDB AUTO_INCREMENT=72 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;