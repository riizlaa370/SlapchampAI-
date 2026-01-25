            if last_use_str:
                last_use = datetime.fromisoformat(last_use_str)
                if now - last_use < timedelta(seconds=COOLDOWN_SECONDS):
                    print(f"Cooldown active for {target_username}")
                    continue

            # Update cooldown
            cooldowns[cooldown_key] = now.isoformat()
            save_cooldowns(cooldowns)

            # Get target user info
            target_user = client.get_user(username=target_username, user_fields=["description", "profile_image_url"]).data
            bio_snippet = target_user.description[:60] if target_user.description else ""
            pfp_desc = "unknown"  # add detection later if wanted

            # Generate roast
            roast = generate_nuclear_roast(target_username, tweet.author.username, bio_snippet, pfp_desc)

            gif = random.choice(SLAP_GIFS)

            # Reply with promo
            reply_text = f"@{target_username} {roast}\n\n{gif}\n" \
                         f"Slapped by @{tweet.author.username} — Powered by @dirtyslapbot 🔥"

            client.create_tweet(
                in_reply_to_tweet_id=tweet.id,
                text=reply_text
            )

            print(f"Pure slap nuked @{target_username} by @{tweet.author.username}")

        time.sleep(60)

    except Exception as e:
        print("Loop error:", e)
        time.sleep(60)
