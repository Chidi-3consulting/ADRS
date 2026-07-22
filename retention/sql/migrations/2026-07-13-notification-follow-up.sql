-- Migration: Add follow_up_sent_at to notifications table for unread reminder follow-ups
ALTER TABLE `notifications` ADD COLUMN `follow_up_sent_at` TIMESTAMP NULL AFTER `sent_at`;
